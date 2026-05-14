"""
app/core/nl2sql/engine.py
────────────────────────────────────────────────────────────────────────────
The NL2SQL Engine — streamlined for a fixed 3-table schema:

  Step 1  Vector cache lookup        (pgvector cosine search — no LLM)
  Step 2  SQL from LLM               (single JSON response when cache misses)
  Step 3  SQL execution              (with security checks + EXPLAIN dry-run)
  Step 4  Retry with error feedback  (up to MAX_SQL_RETRIES attempts)
  Step 5  Local response formatting  (no LLM)
  Step 6  Cache successful pair      (store in vector cache for future)
  Step 7  Log everything             (query_logs table)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.nl2sql.llm_client import EmbeddingClient, LLMClient
from app.core.nl2sql.prompts import (
    NO_DATA_DEFAULT,
    SQL_GENERATION_FULL_SCHEMA_PROMPT,
    SQL_GENERATION_PROMPT,
)
from app.core.nl2sql.sql_executor import SQLExecutor
from app.core.nl2sql.vector_cache import VectorCache
from app.core.schema.schema_builder import full_schema
from app.models.tables import QueryLog, QuerySession
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class NL2SQLResult:
    question: str
    reframed_question: str = ""
    sql_query: Optional[str] = None
    sql_source: str = "llm"                 # "vector_cache" | "llm"
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
    """
    Main pipeline entry point.

    Usage:
        engine = NL2SQLEngine(db_session)
        result = engine.query(question="show me all vip customers", session_id="thread-123")
    """

    CUSTOM_RULES = """
- For customer lookups, prefer filtering by email or name using ILIKE '%value%'.
- For monetary aggregates, always use SUM(total_amount) or AVG(total_amount).
- For time-based queries, use DATE_TRUNC('month', ordered_at) for monthly grouping.
- For order status summaries, GROUP BY status and COUNT(*).
- Never return raw password, payment_card, or sensitive PII columns.
- When asked about "recent" orders without a specific date, default to the last 30 days.
- When asked about "top" customers, sort by lifetime_value DESC.
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
        max_retries: Optional[int] = None,
    ) -> NL2SQLResult:
        """
        Convert a natural language question into SQL, execute it,
        and return a structured result with a deterministic response.
        """
        t0 = time.monotonic()
        result = NL2SQLResult(question=question, reframed_question=question)
        max_retries = max_retries or settings.max_sql_retries

        if session_id:
            self._ensure_session(session_id)

        try:
            embedding = self.embedder.embed(question)

            cached_sql = self.vector_cache.get_exact_match(embedding)
            if cached_sql:
                result.sql_query = cached_sql
                result.sql_source = "vector_cache"
            else:
                sql, source, gen_tokens_in, gen_tokens_out = self._generate_sql(question=question)
                result.sql_query = sql
                result.sql_source = source
                result.input_tokens += gen_tokens_in
                result.output_tokens += gen_tokens_out

            if not result.sql_query:
                result.error = "Failed to generate SQL query"
                result.nl_response = NO_DATA_DEFAULT
            else:
                rows, total_count, error, retry_count, failed, final_sql, retry_tokens = (
                    self._execute_with_retry(
                        sql=result.sql_query,
                        question=question,
                        max_retries=max_retries,
                    )
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
                        natural_language=question,
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

    def _generate_sql(self, question: str):
        """
        Generate SQL from the full 3-table schema.
        Returns (sql, source, input_tokens, output_tokens).
        """
        prompt = SQL_GENERATION_PROMPT.format(
            database_schema=full_schema(),
            custom_rules=self.CUSTOM_RULES,
            max_rows=settings.max_rows_returned,
            question=question,
        )
        try:
            resp = self.llm.chat(user=prompt, json_mode=True, temperature=0.0)
            sql = self.llm.extract_sql_from_json(resp.content)
            return sql, "llm", resp.input_tokens, resp.output_tokens
        except Exception as exc:
            logger.error("SQL generation failed: %s", exc)
            return None, "llm", 0, 0

    def _execute_with_retry(
        self,
        sql: str,
        question: str,
        max_retries: int,
    ):
        """
        Execute SQL. On failure, ask the LLM to fix it using the error message.
        Retries up to max_retries times with the full schema on each retry.
        """
        rows, total, error = self.executor.execute(sql)
        failed_attempts = []
        retry_count = 0
        current_sql = sql
        retry_tokens = {"input": 0, "output": 0}

        if not error and rows is not None:
            return rows, total, None, 0, [], current_sql, retry_tokens

        failed_attempts.append({"attempt": 0, "sql": sql, "error": error})

        for attempt in range(1, max_retries + 1):
            retry_count = attempt
            logger.info("SQL retry %d/%d — error was: %s", attempt, max_retries, error)

            prompt = SQL_GENERATION_FULL_SCHEMA_PROMPT.format(
                database_schema=full_schema(),
                failed_query=current_sql or "(no query generated)",
                error_message=error or "No results returned",
                custom_rules=self.CUSTOM_RULES,
                max_rows=settings.max_rows_returned,
                question=question,
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

            rows, total, error = self.executor.execute(repaired_sql)
            current_sql = repaired_sql

            if not error and rows is not None:
                return rows, total, None, retry_count, failed_attempts, current_sql, retry_tokens

            failed_attempts.append({"attempt": attempt, "sql": repaired_sql, "error": error})

        return rows or [], total or 0, error, retry_count, failed_attempts, current_sql, retry_tokens

    def _build_response(self, rows: List[Dict], total_count: int) -> str:
        """Create a deterministic response without another LLM call."""
        if not rows:
            return NO_DATA_DEFAULT

        if len(rows) == 1 and len(rows[0]) == 1:
            key, value = next(iter(rows[0].items()))
            return f"{key}: {value}"

        if len(rows) == 1:
            return "Found 1 matching record."

        return f"Found {total_count} matching records."

    def _ensure_session(self, session_id: str) -> None:
        """Create the session record if it doesn't exist."""
        try:
            existing = self.db.query(QuerySession).filter_by(id=session_id).first()
            if not existing:
                self.db.add(QuerySession(id=session_id))
                self.db.commit()
        except Exception:
            self.db.rollback()

    def _log(self, result: NL2SQLResult, session_id: Optional[str]) -> None:
        """Persist the query result to the query_logs table."""
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
