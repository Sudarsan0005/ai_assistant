"""
tests/test_nl2sql_engine.py
────────────────────────────────────────────────────────────────────────────
Unit tests for the e-commerce NL2SQL helpers.
"""

from unittest.mock import MagicMock


class TestSQLExecutorSecurity:
    def test_blocks_delete_statement(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("DELETE FROM customers WHERE customer_id = '1'") is False

    def test_allows_safe_select(self):
        from app.core.nl2sql.sql_executor import _is_safe_query
        assert _is_safe_query("SELECT c.email FROM customers c LIMIT 10") is True


class TestSQLLimitInjection:
    def test_adds_limit_when_missing(self):
        from app.core.nl2sql.sql_executor import _ensure_limit
        assert "LIMIT 100" in _ensure_limit("SELECT * FROM products", 100)


class TestLLMClientHelpers:
    def test_extracts_sql_from_json(self):
        from app.core.nl2sql.llm_client import LLMClient
        content = '{"sql": "SELECT * FROM orders LIMIT 5;"}'
        assert LLMClient.extract_sql_from_json(content) == "SELECT * FROM orders LIMIT 5;"

    def test_parse_json_returns_none_for_invalid(self):
        from app.core.nl2sql.llm_client import LLMClient
        assert LLMClient.parse_json("not-json") is None


class TestSchemaBuilder:
    def test_narrow_schema_expands_dependencies(self):
        from app.core.schema.schema_builder import narrow_schema
        result = narrow_schema(["payments"])
        assert "Table: payments" in result
        assert "Table: orders" in result

    def test_full_schema_contains_ecommerce_tables(self):
        from app.core.schema.schema_builder import full_schema
        result = full_schema()
        assert "Table: products" in result
        assert "Table: product_variants" in result
        assert "Table: shipments" in result


class TestPromptTemplates:
    def test_tag_extraction_prompt_formats(self):
        from app.core.nl2sql.prompts import TAG_EXTRACTION_PROMPT
        result = TAG_EXTRACTION_PROMPT.format(
            entity_tags="customers: customer, buyer",
            history_count=0,
            conversation_history="None",
            question="Show top customers by spending",
            customer_scope="No authenticated customer scope.",
        )
        assert "Show top customers by spending" in result
        assert '"tables"' in result

    def test_sql_generation_prompt_formats(self):
        from app.core.nl2sql.prompts import SQL_GENERATION_PROMPT
        result = SQL_GENERATION_PROMPT.format(
            database_schema="Table: customers",
            custom_rules="- rule",
            max_rows=100,
            question="Count customers",
            customer_scope="No authenticated customer scope.",
            customer_id_literal="NULL",
        )
        assert "Count customers" in result
        assert '"sql"' in result


class TestNL2SQLEngine:
    def _make_engine(self):
        from app.core.nl2sql.engine import NL2SQLEngine

        engine = NL2SQLEngine.__new__(NL2SQLEngine)
        engine.db = MagicMock()
        engine.llm = MagicMock()
        engine.embedder = MagicMock()
        engine.vector_cache = MagicMock()
        engine.executor = MagicMock()
        return engine

    def test_fallback_tables_prefers_inventory_tables(self):
        engine = self._make_engine()
        tables = engine._fallback_tables("show low stock variants by seller")
        assert "product_variants" in tables

    def test_query_uses_narrowing_and_local_response(self):
        from app.core.nl2sql.llm_client import LLMResponse

        engine = self._make_engine()
        engine.db.query.return_value.filter_by.return_value.first.return_value = None
        engine.llm.chat.side_effect = [
            LLMResponse(
                content='{"tables":["customers","orders"],"reframe_question":"top customers by revenue"}',
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                latency_ms=50,
            ),
            LLMResponse(
                content='{"sql":"SELECT COUNT(*) AS total_customers FROM customers;"}',
                input_tokens=40,
                output_tokens=20,
                total_tokens=60,
                latency_ms=100,
            ),
        ]
        engine.llm.parse_json.return_value = {"tables": ["customers", "orders"], "reframe_question": "top customers by revenue"}
        engine.embedder.embed.return_value = [0.1, 0.2]
        engine.vector_cache.get_exact_match.return_value = None
        engine.executor.execute.return_value = ([{"total_customers": 150}], 1, None)

        result = engine.query("How many customers are there?", session_id=None)

        assert result.reframed_question == "top customers by revenue"
        assert result.nl_response == "total_customers: 150"
        assert result.sql_query == "SELECT COUNT(*) AS total_customers FROM customers;"

    def test_customer_scope_validator_requires_customer_id_filter(self):
        engine = self._make_engine()
        sql = "SELECT o.order_id FROM orders o LIMIT 10;"
        error = engine._validate_customer_scope(sql, "11111111-1111-1111-1111-111111111111")
        assert "Customer scope violation" in error

    def test_customer_scope_validator_allows_product_only_queries(self):
        engine = self._make_engine()
        sql = "SELECT p.product_name FROM products p LIMIT 10;"
        assert engine._validate_customer_scope(sql, "11111111-1111-1111-1111-111111111111") is None
