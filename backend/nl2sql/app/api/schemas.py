"""
app/api/schemas.py
──────────────────
Pydantic models used by the active API surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, description="Conversation thread ID for follow-up context")
    customer_id: Optional[UUID] = Field(None, description="Authenticated customer scope for customer-owned data")
    max_retries: Optional[int] = Field(None, ge=0, le=5)
    include_sql: bool = False
    include_raw_data: bool = True


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class QueryResponse(BaseModel):
    question: str
    reframed_question: Optional[str] = None
    nl_response: str
    is_greeting: bool = False
    rows: Optional[List[Dict[str, Any]]] = None
    total_count: int = 0
    sql_query: Optional[str] = None
    sql_source: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    token_usage: TokenUsage
    latency_ms: int
    failed_attempts: Optional[List[Dict[str, Any]]] = None


class QueryLogResponse(BaseModel):
    id: UUID
    session_id: Optional[str]
    user_question: str
    reframed_question: Optional[str]
    generated_sql: Optional[str]
    sql_source: Optional[str]
    result_rows: int
    nl_response: Optional[str]
    error: Optional[str]
    retry_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}
