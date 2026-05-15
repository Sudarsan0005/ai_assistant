"""
app/core/nl2sql/engine.py
────────────────────────────────────────────────────────────────────────────
NL2SQL pipeline for the e-commerce schema:

  Step 1  Intent and table narrowing  (LLM JSON)
  Step 2  Vector cache lookup         (embedding + pgvector)
  Step 3  SQL generation              (LLM JSON with narrowed schema)
  Step 4  SQL execution               (security checks + EXPLAIN)
  Step 5  Retry with full schema      (LLM JSON)
  Step 6  Local response formatting
  Step 7  Cache + log
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.nl2sql.llm_client import EmbeddingClient, LLMClient
from app.core.nl2sql.prompts import (
    NO_DATA_DEFAULT,
    SQL_GENERATION_FULL_SCHEMA_PROMPT,
    SQL_GENERATION_PROMPT,
    TAG_EXTRACTION_PROMPT,
)
from app.core.nl2sql.sql_executor import SQLExecutor
from app.core.nl2sql.vector_cache import VectorCache
from app.core.schema.schema_builder import ENTITY_TAG_DICTIONARY, full_schema, narrow_schema
from app.models.tables import QueryLog, QuerySession
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class NL2SQLResult:
    question: str
    reframed_question: str = ""
    sql_query: Optional[str] = None
    sql_source: str = "llm"
    rows: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    nl_response: str = ""
    is_greeting: bool = False
    error: Optional[str] = None
    retry_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    failed_attempts: List[Dict] = field(default_factory=list)


class NL2SQLEngine:
    CUSTOMER_SCOPED_TABLES = {
        "customers",
        "customer_addresses",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "payments",
        "shipments",
        "product_reviews",
        "wishlists",
    }

    CUSTOM_RULES = """
- Use only the selected tables unless the retry step expands to the full schema.
- Never select password_hash.
- For customer counts or segments, use customers.status, verification flags, gender, dates, and location via customer_addresses when needed.
- For product catalog questions, use products, categories, sellers, product_variants, product_images, attributes, and product_attribute_values as appropriate.
- For stock or inventory availability, use product_variants.stock_quantity and status.
- For cart analysis, use carts and cart_items.
- For order revenue, use orders.total_amount, subtotal, tax_amount, shipping_amount, discount_amount, or order_items.total_price as appropriate.
- For payment analysis, use payments.paid_amount, payment_status, payment_method, and payment_gateway.
- For delivery analysis, use shipments.shipping_status, courier_name, shipped_at, and delivered_at.
- For customer sentiment, use product_reviews.rating, review_title, and review_text.
- For wishlist analysis, use wishlists joined to customers and product_variants.
- For coupon analysis, use coupons.code, discount_type, discount_value, min_order_amount, max_discount_amount, valid_from, and valid_to.
"""

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()
        self.embedder = EmbeddingClient()
        self.vector_cache = VectorCache(db)
        self.executor = SQLExecutor(db)

    def query(
        self,
        question: str,
        session_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> NL2SQLResult:
        t0 = time.monotonic()
        result = NL2SQLResult(question=question, reframed_question=question)
        max_retries = max_retries or settings.max_sql_retries

        if session_id:
            self._ensure_session(session_id)

        try:
            intent = self._extract_intent(question=question, session_id=session_id, customer_id=customer_id)
            result.input_tokens += intent.get("_input_tokens", 0)
            result.output_tokens += intent.get("_output_tokens", 0)

            selected_tables = intent.get("tables") or self._fallback_tables(question)
            result.reframed_question = intent.get("reframe_question") or question
            effective_question = result.reframed_question

            embedding = self.embedder.embed(effective_question)
            cached_sql = self.vector_cache.get_exact_match(embedding)
            if cached_sql:
                result.sql_query = cached_sql
                result.sql_source = "vector_cache"
            else:
                sql, source, gen_tokens_in, gen_tokens_out = self._generate_sql(
                    question=effective_question,
                    tables=selected_tables,
                    customer_id=customer_id,
                )
                result.sql_query = sql
                result.sql_source = source
                result.input_tokens += gen_tokens_in
                result.output_tokens += gen_tokens_out

            if not result.sql_query:
                result.error = "Failed to generate SQL query"
                result.nl_response = NO_DATA_DEFAULT
            else:
                rows, total_count, error, retry_count, failed, final_sql, retry_tokens = self._execute_with_retry(
                    sql=result.sql_query,
                    question=effective_question,
                    customer_id=customer_id,
                    max_retries=max_retries,
                )
                result.rows = rows
                result.total_count = total_count
                result.error = error
                result.retry_count = retry_count
                result.failed_attempts = failed
                result.sql_query = final_sql
                result.input_tokens += retry_tokens["input"]
                result.output_tokens += retry_tokens["output"]
                result.nl_response = self._build_response(rows=rows, total_count=total_count)

                if rows and result.sql_source != "vector_cache":
                    self.vector_cache.store(
                        natural_language=effective_question,
                        sql_query=result.sql_query,
                        embedding=embedding,
                    )

        except Exception as exc:
            logger.exception("NL2SQL engine error: %s", exc)
            result.error = str(exc)
            result.nl_response = NO_DATA_DEFAULT

        result.total_tokens = result.input_tokens + result.output_tokens
        result.latency_ms = int((time.monotonic() - t0) * 1000)
        self._log(result, session_id)
        return result

    def _extract_intent(self, question: str, session_id: Optional[str], customer_id: Optional[str]) -> Dict[str, Any]:
        history = self._get_conversation_history(session_id, limit=4)
        entity_tags = "\n".join(
            f"  {table}: {', '.join(tags)}"
            for table, tags in ENTITY_TAG_DICTIONARY.items()
        )
        prompt = TAG_EXTRACTION_PROMPT.format(
            entity_tags=entity_tags,
            history_count=len(history.splitlines()) if history else 0,
            conversation_history=history or "None",
            question=question,
            customer_scope=self._customer_scope_text(customer_id),
        )
        try:
            resp = self.llm.chat(user=prompt, json_mode=True, temperature=0.0)
            parsed = self.llm.parse_json(resp.content) or {}
            parsed["_input_tokens"] = resp.input_tokens
            parsed["_output_tokens"] = resp.output_tokens
            tables = [table for table in parsed.get("tables", []) if table in ENTITY_TAG_DICTIONARY]
            parsed["tables"] = tables or self._fallback_tables(question)
            return parsed
        except Exception as exc:
            logger.warning("Table narrowing failed: %s", exc)
            return {
                "tables": self._fallback_tables(question),
                "reframe_question": question,
                "_input_tokens": 0,
                "_output_tokens": 0,
            }

    def _fallback_tables(self, question: str) -> List[str]:
        lowered = question.lower()
        scores: Dict[str, int] = {}
        for table, tags in ENTITY_TAG_DICTIONARY.items():
            score = sum(1 for tag in tags if tag in lowered)
            if table in lowered:
                score += 2
            if score:
                scores[table] = score
        if not scores:
            return ["customers", "orders", "order_items"]
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [table for table, _ in ranked[:4]]

    def _generate_sql(self, question: str, tables: List[str], customer_id: Optional[str]):
        prompt = SQL_GENERATION_PROMPT.format(
            database_schema=narrow_schema(tables),
            custom_rules=self.CUSTOM_RULES,
            max_rows=settings.max_rows_returned,
            question=question,
            customer_scope=self._customer_scope_text(customer_id),
            customer_id_literal=self._customer_id_literal(customer_id),
        )
        try:
            resp = self.llm.chat(user=prompt, json_mode=True, temperature=0.0)
            sql = self.llm.extract_sql_from_json(resp.content)
            scope_error = self._validate_customer_scope(sql, customer_id)
            if scope_error:
                logger.warning("Rejected unscoped SQL: %s", scope_error)
                return None, "llm", resp.input_tokens, resp.output_tokens
            return sql, "llm", resp.input_tokens, resp.output_tokens
        except Exception as exc:
            logger.error("SQL generation failed: %s", exc)
            return None, "llm", 0, 0

    def _execute_with_retry(self, sql: str, question: str, customer_id: Optional[str], max_retries: int):
        rows, total, error = self.executor.execute(sql)
        failed_attempts: List[Dict[str, Any]] = []
        retry_count = 0
        current_sql = sql
        retry_tokens = {"input": 0, "output": 0}

        if not error and rows is not None:
            return rows, total, None, 0, [], current_sql, retry_tokens

        failed_attempts.append({"attempt": 0, "sql": sql, "error": error})

        for attempt in range(1, max_retries + 1):
            retry_count = attempt
            prompt = SQL_GENERATION_FULL_SCHEMA_PROMPT.format(
                database_schema=full_schema(),
                failed_query=current_sql or "(no query generated)",
                error_message=self._augment_retry_error(error, customer_id),
                custom_rules=self.CUSTOM_RULES,
                max_rows=settings.max_rows_returned,
                question=question,
                customer_scope=self._customer_scope_text(customer_id),
                customer_id_literal=self._customer_id_literal(customer_id),
            )
            try:
                resp = self.llm.chat(user=prompt, json_mode=True, temperature=0.0)
                retry_tokens["input"] += resp.input_tokens
                retry_tokens["output"] += resp.output_tokens
                repaired_sql = self.llm.extract_sql_from_json(resp.content)
            except Exception as exc:
                logger.warning("Retry %d LLM call failed: %s", attempt, exc)
                break

            if not repaired_sql:
                continue

            scope_error = self._validate_customer_scope(repaired_sql, customer_id)
            if scope_error:
                error = scope_error
                current_sql = repaired_sql
                failed_attempts.append({"attempt": attempt, "sql": repaired_sql, "error": error})
                continue

            rows, total, error = self.executor.execute(repaired_sql)
            current_sql = repaired_sql
            if not error and rows is not None:
                return rows, total, None, retry_count, failed_attempts, current_sql, retry_tokens

            failed_attempts.append({"attempt": attempt, "sql": repaired_sql, "error": error})

        return rows or [], total or 0, error, retry_count, failed_attempts, current_sql, retry_tokens

    def _build_response(self, rows: List[Dict], total_count: int) -> str:
        if not rows:
            return NO_DATA_DEFAULT
        if len(rows) == 1 and len(rows[0]) == 1:
            key, value = next(iter(rows[0].items()))
            return f"{key}: {value}"
        if len(rows) == 1:
            return "Found 1 matching record."
        return f"Found {total_count} matching records."

    def _get_conversation_history(self, session_id: Optional[str], limit: int = 4) -> str:
        if not session_id:
            return ""
        try:
            logs = (
                self.db.query(QueryLog)
                .filter(QueryLog.session_id == session_id)
                .order_by(QueryLog.created_at.desc())
                .limit(limit)
                .all()
            )
            history: List[str] = []
            for log in reversed(logs):
                history.append(f"Q: {log.user_question}")
                if log.nl_response:
                    history.append(f"A: {log.nl_response[:200]}")
            return "\n".join(history)
        except Exception:
            return ""

    def _customer_scope_text(self, customer_id: Optional[str]) -> str:
        if not customer_id:
            return "No authenticated customer scope. Global analytics queries are allowed."
        return (
            f"Authenticated customer scope is active for customer_id = '{customer_id}'. "
            "Queries touching customer-owned tables must be limited to that customer only. "
            "Global product, seller, category, and coupon questions may remain unscoped if they do not expose other customers' data."
        )

    @staticmethod
    def _customer_id_literal(customer_id: Optional[str]) -> str:
        return f"'{customer_id}'" if customer_id else "NULL"

    def _validate_customer_scope(self, sql: Optional[str], customer_id: Optional[str]) -> Optional[str]:
        if not sql or not customer_id:
            return None

        lowered = sql.lower()
        touched_tables = {
            table for table in self.CUSTOMER_SCOPED_TABLES
            if re.search(rf"\b{re.escape(table.lower())}\b", lowered)
        }
        if not touched_tables:
            return None
        if customer_id.lower() in lowered:
            return None
        return (
            "Customer scope violation: query touches customer-owned tables "
            f"{sorted(touched_tables)} without filtering to customer_id = '{customer_id}'."
        )

    def _augment_retry_error(self, error: Optional[str], customer_id: Optional[str]) -> str:
        message = error or "No results returned"
        if not customer_id:
            return message
        return (
            f"{message}\nCustomer scope requirement: any query touching customer-owned tables "
            f"must be restricted to customer_id = '{customer_id}'."
        )

    def _ensure_session(self, session_id: str) -> None:
        try:
            existing = self.db.query(QuerySession).filter_by(id=session_id).first()
            if not existing:
                self.db.add(QuerySession(id=session_id))
                self.db.commit()
        except Exception:
            self.db.rollback()

    def _log(self, result: NL2SQLResult, session_id: Optional[str]) -> None:
        try:
            log = QueryLog(
                session_id=session_id,
                user_question=result.question,
                reframed_question=result.reframed_question or None,
                generated_sql=result.sql_query,
                sql_source=result.sql_source,
                result_rows=result.total_count,
                nl_response=result.nl_response,
                error=result.error,
                retry_count=result.retry_count,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                total_latency_ms=result.latency_ms,
            )
            self.db.add(log)
            self.db.commit()
        except Exception as exc:
            logger.warning("Failed to write query log: %s", exc)
            self.db.rollback()
