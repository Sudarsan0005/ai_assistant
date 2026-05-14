"""
app/core/nl2sql/sql_executor.py
────────────────────────────────────────────────────────────────────────────
Executes generated SQL against the internal Postgres database.

Security layers:
  1. Blocklist check — rejects any query containing mutating keywords
     (DELETE, DROP, INSERT, etc.) or dangerous system functions.
  2. EXPLAIN dry-run — validates the query is syntactically and semantically
     correct before fetching real data.
  3. Automatic LIMIT injection — if the query lacks a LIMIT, one is appended.
  4. Result cap — never returns more than MAX_ROWS_RETURNED rows.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
#  Security blocklist patterns
# ─────────────────────────────────────────────────────────────────────────────

BLOCKED_PATTERNS = [
    # DML / DDL mutations
    r"\b(INSERT|UPDATE|DELETE|TRUNCATE|DROP|CREATE|ALTER|REPLACE|MERGE)\b",
    # Privilege escalation
    r"\b(GRANT|REVOKE|EXEC|EXECUTE)\b",
    # System information leakage
    r"\bINFORMATION_SCHEMA\b",
    r"\bpg_catalog\b",
    # Dangerous Postgres functions
    r"\b(pg_sleep|pg_terminate_backend|pg_cancel_backend|pg_read_file|lo_export|copy)\b",
    # Time-delay / DoS
    r"\b(WAITFOR|SLEEP|BENCHMARK)\b",
    # Subquery injection trick
    r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP)",
]


def _is_safe_query(sql: str) -> bool:
    """Return True if the query passes all security checks."""
    upper = sql.upper()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, upper, re.IGNORECASE):
            logger.warning("Blocked query pattern '%s' in: %.120s", pattern, sql)
            return False
    return True

def _ensure_limit(sql: str, max_rows: int) -> str:
    """Append a LIMIT clause if the query does not already have one."""
    sql = sql.strip().rstrip(";")
    if not re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT {max_rows}"
    sql = sql + ";"
    return sql


def _clean_sql(sql: str) -> str:
    """Normalize whitespace and remove stray escape sequences."""
    sql = re.sub(r"\\n", " ", sql)
    sql = re.sub(r"\\r", " ", sql)
    sql = re.sub(r"\s+", " ", sql)
    return sql.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Executor
# ─────────────────────────────────────────────────────────────────────────────

class SQLExecutor:
    """
    Executes SELECT queries against the internal Postgres database.

    Args:
        db: SQLAlchemy Session connected to the internal Postgres DB.
    """

    def __init__(self, db: Session):
        self.db = db
        self.max_rows = settings.max_rows_returned

    def execute(self, sql: str) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        """
        Execute the SQL and return (rows, total_count, error_message).

        Returns:
            rows          — list of dicts (capped at max_rows)
            total_count   — actual count (may differ from len(rows) if capped)
            error_message — None on success, string on failure
        """
        if not sql or not sql.strip():
            return [], 0, "Empty SQL query"

        sql = _clean_sql(sql)

        if not _is_safe_query(sql):
            return [], 0, "Query blocked by security policy"

        sql = _ensure_limit(sql, self.max_rows)

        # ── EXPLAIN dry-run ──────────────────────────────────────────────────
        explain_error = self._explain(sql)
        if explain_error:
            return [], 0, explain_error

        # ── Execute ──────────────────────────────────────────────────────────
        try:
            result = self.db.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(self.max_rows)]

            # Serialize non-serializable types
            rows = [self._serialize_row(r) for r in rows]

            # Get total count for large result sets
            total_count = self._get_count(sql) if len(rows) == self.max_rows else len(rows)

            return rows, total_count, None

        except Exception as exc:
            logger.warning("SQL execution error: %s | SQL: %.200s", exc, sql)
            self.db.rollback()
            return [], 0, str(exc)

    def _explain(self, sql: str) -> Optional[str]:
        """
        Run EXPLAIN (not EXPLAIN ANALYZE) to validate the query.
        Returns error string if invalid, None if OK.
        """
        try:
            self.db.execute(text(f"EXPLAIN {sql}"))
            return None
        except Exception as exc:
            self.db.rollback()
            return str(exc)

    def _get_count(self, sql: str) -> int:
        """Wrap the query in a COUNT(*) to get total matching rows."""
        try:
            # Strip LIMIT clause for counting
            count_sql = re.sub(r"\bLIMIT\s+\d+\s*;?\s*$", "", sql, flags=re.IGNORECASE).strip()
            count_sql = f"SELECT COUNT(*) FROM ({count_sql}) AS _count_subquery"
            result = self.db.execute(text(count_sql))
            row = result.fetchone()
            return int(row[0]) if row else 0
        except Exception:
            self.db.rollback()
            return 0

    @staticmethod
    def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert non-JSON-serializable types (Decimal, datetime, UUID) to str."""
        import decimal
        import datetime
        import uuid

        clean = {}
        for k, v in row.items():
            if isinstance(v, decimal.Decimal):
                clean[k] = float(v)
            elif isinstance(v, (datetime.datetime, datetime.date)):
                clean[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                clean[k] = str(v)
            elif v is None:
                clean[k] = None
            else:
                clean[k] = v
        return clean
