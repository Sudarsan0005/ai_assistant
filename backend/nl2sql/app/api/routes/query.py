"""
app/api/routes/query.py
─────────────────────────────
POST /query   — the main NL2SQL endpoint
GET  /history — retrieve query history for a session
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import (
    ErrorResponse, QueryLogResponse, QueryRequest, QueryResponse, TokenUsage
)
from app.core.nl2sql.engine import NL2SQLEngine
from app.database.connection import get_db
from app.models.tables import QueryLog

router = APIRouter(prefix="/query", tags=["NL2SQL"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=QueryResponse,
    summary="Ask a natural language question about customers / orders",
    responses={500: {"model": ErrorResponse}},
)
def ask_question(
    request: QueryRequest,
    db: Session = Depends(get_db),
):
    """
    Convert a natural language question into SQL, execute it against
    the internal Postgres database, and return a human-readable answer.

    **Session context**: pass the same `session_id` across multiple calls
    to enable follow-up questions that reference previous answers.

    **Examples of supported questions**:
    - "Show me all VIP customers in New York"
    - "How many orders were placed last month?"
    - "What is the total revenue from John Smith's account?"
    - "List the top 10 customers by lifetime value"
    - "Show cancelled orders from this week"
    - "Which products were ordered most in Q1 2024?"
    """
    try:
        engine = NL2SQLEngine(db=db)
        result = engine.query(
            question=request.question,
            session_id=request.session_id,
            max_retries=request.max_retries,
        )

        return QueryResponse(
            question=result.question,
            reframed_question=result.reframed_question or None,
            nl_response=result.nl_response,
            is_greeting=result.is_greeting,
            rows=result.rows if request.include_raw_data else None,
            total_count=result.total_count,
            sql_query=result.sql_query if request.include_sql else None,
            sql_source=result.sql_source if request.include_sql else None,
            retry_count=result.retry_count,
            error=result.error,
            token_usage=TokenUsage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
            ),
            latency_ms=result.latency_ms,
            failed_attempts=result.failed_attempts if result.failed_attempts else None,
        )

    except Exception as exc:
        logger.exception("Unexpected error in /query: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/history",
    response_model=list[QueryLogResponse],
    summary="Get query history for a session",
)
def get_history(
    session_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Return the last N query logs for the given session ID."""
    logs = (
        db.query(QueryLog)
        .filter(QueryLog.session_id == session_id)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs
