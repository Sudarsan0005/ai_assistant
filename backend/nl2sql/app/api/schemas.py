"""
app/api/schemas.py
──────────────────
Pydantic v2 request/response models for all API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
#  Shared
# ─────────────────────────────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
#  Data Source
# ─────────────────────────────────────────────────────────────────────────────

class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Friendly name for this source")
    db_type: str = Field("postgresql", description="postgresql | mysql | mssql | sqlite")
    host: str = Field(..., description="Database host or IP")
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., description="Database / schema name")
    username: str
    password: str = Field(..., description="Will be AES-encrypted before storage")
    schema_name: str = Field("public", description="Postgres schema (default: public)")
    table_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description='Override source table names e.g. {"customers": "tbl_clients"}'
    )

    @field_validator("db_type")
    @classmethod
    def validate_db_type(cls, v: str) -> str:
        allowed = {"postgresql", "mysql", "mssql", "sqlite"}
        if v not in allowed:
            raise ValueError(f"db_type must be one of {allowed}")
        return v


class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    db_type: str
    host: str
    port: int
    database_name: str
    schema_name: str
    is_active: bool
    table_mapping: Dict[str, str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DataSourceTestRequest(BaseModel):
    db_type: str = "postgresql"
    host: str
    port: int
    database_name: str
    username: str
    password: str
    schema_name: str = "public"


class DataSourceTestResponse(BaseModel):
    success: bool
    message: str
    tables_found: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
#  Sync
# ─────────────────────────────────────────────────────────────────────────────

class SyncTriggerRequest(BaseModel):
    source_id: UUID


class SyncJobResponse(BaseModel):
    id: UUID
    source_id: UUID
    triggered_by: str
    status: str
    customers_synced: int
    orders_synced: int
    items_synced: int
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
#  NL2SQL Query
# ─────────────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Natural language question")
    session_id: Optional[str] = Field(None, description="Conversation thread ID for history context")
    max_retries: Optional[int] = Field(None, ge=0, le=5, description="Override max SQL retries")
    include_sql: bool = Field(False, description="Include the generated SQL in the response")
    include_raw_data: bool = Field(True, description="Include raw result rows")


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
    sql_source: Optional[str] = None     # "vector_cache" | "vector_adapt" | "llm"
    retry_count: int = 0
    error: Optional[str] = None
    token_usage: TokenUsage
    latency_ms: int
    failed_attempts: Optional[List[Dict]] = None


# ─────────────────────────────────────────────────────────────────────────────
#  Query History
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
#  Customer / Order (read-only views)
# ─────────────────────────────────────────────────────────────────────────────

class CustomerResponse(BaseModel):
    id: UUID
    external_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    company: Optional[str]
    city: Optional[str]
    country: Optional[str]
    status: Optional[str]
    lifetime_value: Optional[float]
    total_orders: int
    customer_since: Optional[datetime]

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: UUID
    product_name: Optional[str]
    sku: Optional[str]
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]
    category: Optional[str]

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    external_id: str
    order_number: Optional[str]
    status: Optional[str]
    total_amount: Optional[float]
    currency: str
    payment_status: Optional[str]
    ordered_at: Optional[datetime]
    shipped_at: Optional[datetime]
    delivered_at: Optional[datetime]
    items: List[OrderItemResponse] = []

    model_config = {"from_attributes": True}
