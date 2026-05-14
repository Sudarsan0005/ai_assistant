"""
tests/test_nl2sql_engine.py
────────────────────────────────────────────────────────────────────────────
Unit tests for the NL2SQL pipeline.

Run with: pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ─────────────────────────────────────────────────────────────────────────────
#  SQL Executor tests (pure logic — no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLExecutorSecurity:
    """Tests for the security blocklist in sql_executor.py"""

    def test_blocks_delete_statement(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("DELETE FROM customers WHERE id = '1'") is False

    def test_blocks_drop_table(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("DROP TABLE customers") is False

    def test_blocks_insert(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("INSERT INTO orders VALUES (1,2,3)") is False

    def test_blocks_truncate(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("TRUNCATE customers") is False

    def test_blocks_information_schema(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("SELECT * FROM INFORMATION_SCHEMA.tables") is False

    def test_blocks_pg_sleep(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("SELECT pg_sleep(10)") is False

    def test_blocks_stacked_query(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("SELECT 1; DROP TABLE customers") is False

    def test_allows_safe_select(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("SELECT * FROM customers WHERE status = 'active'") is True

    def test_allows_join_query(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        sql = """
            SELECT c.first_name, SUM(o.total_amount)
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            GROUP BY c.first_name
            ORDER BY 2 DESC
            LIMIT 10
        """
        assert _is_safe_query(sql) is True


class TestSQLLimitInjection:
    def test_adds_limit_when_missing(self):
        from app.core.nl2sql.sql_executor import _ensure_limit
        sql = "SELECT * FROM customers"
        result = _ensure_limit(sql, 100)
        assert "LIMIT 100" in result

    def test_keeps_existing_limit(self):
        from app.core.nl2sql.sql_executor import _ensure_limit
        sql = "SELECT * FROM customers LIMIT 50"
        result = _ensure_limit(sql, 100)
        assert "LIMIT 50" in result
        assert result.count("LIMIT") == 1

    def test_adds_semicolon(self):
        from app.core.nl2sql.sql_executor import _ensure_limit
        sql = "SELECT * FROM orders"
        result = _ensure_limit(sql, 100)
        assert result.rstrip().endswith(";")


class TestRowSerialization:
    def test_serializes_decimal(self):
        import decimal
        from app.core.nl2sql.sql_executor import SQLExecutor
        row = {"total": decimal.Decimal("123.45")}
        result = SQLExecutor._serialize_row(row)
        assert result["total"] == 123.45
        assert isinstance(result["total"], float)

    def test_serializes_datetime(self):
        import datetime
        from app.core.nl2sql.sql_executor import SQLExecutor
        row = {"ordered_at": datetime.datetime(2024, 1, 15, 10, 30)}
        result = SQLExecutor._serialize_row(row)
        assert result["ordered_at"] == "2024-01-15T10:30:00"

    def test_serializes_uuid(self):
        import uuid
        from app.core.nl2sql.sql_executor import SQLExecutor
        uid = uuid.uuid4()
        row = {"id": uid}
        result = SQLExecutor._serialize_row(row)
        assert result["id"] == str(uid)

    def test_preserves_none(self):
        from app.core.nl2sql.sql_executor import SQLExecutor
        row = {"notes": None}
        result = SQLExecutor._serialize_row(row)
        assert result["notes"] is None


# ─────────────────────────────────────────────────────────────────────────────
#  LLM Client tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSQLExtraction:
    """Tests for LLMClient.extract_sql()"""

    def test_extracts_plain_select(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "SELECT * FROM customers WHERE status = 'active' LIMIT 10;"
        result = LLMClient.extract_sql(content)
        assert result is not None
        assert "SELECT" in result
        assert "customers" in result

    def test_strips_markdown_fence(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "```sql\nSELECT id, email FROM customers LIMIT 5;\n```"
        result = LLMClient.extract_sql(content)
        assert result is not None
        assert "```" not in result

    def test_strips_answer_prefix(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "Answer: SELECT * FROM orders LIMIT 100;"
        result = LLMClient.extract_sql(content)
        assert result is not None
        assert result.startswith("SELECT")

    def test_extracts_cte(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "WITH top_customers AS (SELECT * FROM customers) SELECT * FROM top_customers LIMIT 10;"
        result = LLMClient.extract_sql(content)
        assert result is not None
        assert "WITH" in result

    def test_returns_none_for_empty(self):
        from app.core.nl2sql.llm_client import LLMClient
        assert LLMClient.extract_sql("") is None
        assert LLMClient.extract_sql(None) is None

    def test_adds_semicolon_if_missing(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "SELECT * FROM customers LIMIT 10"
        result = LLMClient.extract_sql(content)
        assert result is not None
        assert result.rstrip().endswith(";")


class TestJSONParsing:
    def test_parses_valid_json(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = '{"is_greeting": false, "entities": ["customers"]}'
        result = LLMClient.parse_json(content)
        assert result is not None
        assert result["is_greeting"] is False

    def test_strips_json_fence(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = "```json\n{\"key\": \"value\"}\n```"
        result = LLMClient.parse_json(content)
        assert result == {"key": "value"}

    def test_returns_none_for_invalid(self):
        from app.core.nl2sql.llm_client import LLMClient
        result = LLMClient.parse_json("not json at all !!!")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
#  Schema builder tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaBuilder:
    def test_narrow_schema_customers_only(self):
        from app.core.schema.schema_builder import narrow_schema
        result = narrow_schema(["customers"])
        assert "customers" in result
        assert "orders" not in result or "Join guidance" not in result

    def test_narrow_schema_orders_includes_customers(self):
        from app.core.schema.schema_builder import narrow_schema
        result = narrow_schema(["orders"])
        assert "customers" in result
        assert "orders" in result

    def test_narrow_schema_items_includes_all(self):
        from app.core.schema.schema_builder import narrow_schema
        result = narrow_schema(["order_items"])
        assert "customers" in result
        assert "orders" in result
        assert "order_items" in result
        assert "Join guidance" in result

    def test_full_schema_has_all_tables(self):
        from app.core.schema.schema_builder import full_schema
        result = full_schema()
        assert "customers" in result
        assert "orders" in result
        assert "order_items" in result
        assert "Join guidance" in result


# ─────────────────────────────────────────────────────────────────────────────
#  Encryption tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        from app.utils.encryption import encrypt_password, decrypt_password
        original = "super_secret_password_123!"
        encrypted = encrypt_password(original)
        assert encrypted != original
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_different_encryptions_for_same_input(self):
        from app.utils.encryption import encrypt_password
        pw = "password123"
        enc1 = encrypt_password(pw)
        enc2 = encrypt_password(pw)
        # Fernet uses random IV — each encryption is unique
        assert enc1 != enc2

    def test_invalid_token_raises(self):
        from app.utils.encryption import decrypt_password
        with pytest.raises(ValueError):
            decrypt_password("not_a_valid_encrypted_string")


# ─────────────────────────────────────────────────────────────────────────────
#  Prompt template tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptTemplates:
    def test_sql_generation_prompt_formats(self):
        from app.core.nl2sql.prompts import SQL_GENERATION_PROMPT
        result = SQL_GENERATION_PROMPT.format(
            database_schema="CREATE TABLE customers (...)",
            custom_rules="- Rule 1",
            max_rows=100,
            question="Show all VIP customers",
        )
        assert "customers" in result
        assert "VIP" in result
        assert "100" in result


# ─────────────────────────────────────────────────────────────────────────────
#  Engine integration test (mocked LLM + DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestNL2SQLEngine:
    """Tests for the streamlined single-call NL2SQL flow."""

    def _make_engine(self, db_mock):
        from app.core.nl2sql.engine import NL2SQLEngine
        engine = NL2SQLEngine.__new__(NL2SQLEngine)
        engine.db = db_mock
        engine.llm = MagicMock()
        engine.embedder = MagicMock()
        engine.vector_cache = MagicMock()
        engine.executor = MagicMock()
        return engine

    def test_query_uses_single_generation_call_and_local_response(self):
        from app.core.nl2sql.llm_client import LLMResponse

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        engine = self._make_engine(db)
        engine.llm.chat.return_value = LLMResponse(
            content='{"sql": "SELECT COUNT(*) AS total_customers FROM customers LIMIT 100;"}',
            input_tokens=50,
            output_tokens=20,
            total_tokens=70,
            latency_ms=200,
        )
        engine.embedder.embed.return_value = [0.1, 0.2]
        engine.vector_cache.get_exact_match.return_value = None
        engine.executor.execute.return_value = ([{"total_customers": 42}], 1, None)

        result = engine.query(question="How many customers do we have?", session_id=None)

        assert result.is_greeting is False
        assert result.sql_query == "SELECT COUNT(*) AS total_customers FROM customers LIMIT 100;"
        assert result.nl_response == "total_customers: 42"
        assert result.total_tokens == 70
        engine.llm.chat.assert_called_once()
        engine.executor.execute.assert_called_once()

    def test_retry_updates_final_sql(self):
        from app.core.nl2sql.llm_client import LLMResponse

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        engine = self._make_engine(db)
        engine.embedder.embed.return_value = [0.1, 0.2]
        engine.vector_cache.get_exact_match.return_value = None
        engine.llm.chat.side_effect = [
            LLMResponse(
                content='{"sql": "SELECT bad_column FROM customers LIMIT 100;"}',
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                latency_ms=100,
            ),
            LLMResponse(
                content='{"sql": "SELECT email FROM customers LIMIT 100;"}',
                input_tokens=12,
                output_tokens=6,
                total_tokens=18,
                latency_ms=120,
            ),
        ]
        engine.executor.execute.side_effect = [
            ([], 0, 'column "bad_column" does not exist'),
            ([{"email": "a@example.com"}], 1, None),
        ]

        result = engine.query(question="Show one customer email", session_id=None, max_retries=1)

        assert result.sql_query == "SELECT email FROM customers LIMIT 100;"
        assert result.retry_count == 1
        assert result.nl_response == "email: a@example.com"
        assert result.total_tokens == 33
