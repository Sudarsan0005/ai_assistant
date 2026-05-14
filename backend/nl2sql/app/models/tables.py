"""
app/models/tables.py
─────────────────────────────────────────────────────────────────────────────
All SQLAlchemy ORM models for the internal Postgres database.

Tables:
  • data_sources       – registered external DB connections
  • customers          – synced customer profiles
  • orders             – synced order records
  • order_items        – line items per order
  • sync_jobs          – audit log of every sync run
  • query_cache        – vector-indexed NL→SQL pairs (semantic cache)
  • query_sessions     – conversation thread metadata
  • query_logs         – every NL2SQL request + result log
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Float,
    ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
#  Data Sources  (registered external DBs to sync from)
# ─────────────────────────────────────────────────────────────────────────────

class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    db_type = Column(
        Enum("postgresql", "mysql", "mssql", "sqlite", name="db_type_enum"),
        nullable=False,
        default="postgresql",
    )
    host = Column(String(500), nullable=False)
    port = Column(Integer, nullable=False)
    database_name = Column(String(200), nullable=False)
    username = Column(String(200), nullable=False)
    password_encrypted = Column(Text, nullable=False)   # AES-encrypted
    schema_name = Column(String(100), default="public")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # table-name mappings stored as JSON: {"customers": "tbl_clients", "orders": "tbl_orders"}
    table_mapping = Column(JSON, default=dict)

    sync_jobs = relationship("SyncJob", back_populates="data_source", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
#  Customer Profiles  (synced from source)
# ─────────────────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(200), nullable=False)   # PK in the source DB

    # Core profile fields
    first_name = Column(String(200))
    last_name = Column(String(200))
    email = Column(String(500))
    phone = Column(String(100))
    company = Column(String(300))
    city = Column(String(200))
    state = Column(String(200))
    country = Column(String(200))
    postal_code = Column(String(50))
    status = Column(String(100))                        # active | inactive | vip …
    customer_since = Column(DateTime(timezone=True))
    lifetime_value = Column(Numeric(12, 2), default=0)
    total_orders = Column(Integer, default=0)

    raw_data = Column(JSON, default=dict)               # full source row as-is
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_customer_source_external"),
        Index("ix_customers_email", "email"),
        Index("ix_customers_source_id", "source_id"),
        Index("ix_customers_status", "status"),
    )

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
#  Orders
# ─────────────────────────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    external_id = Column(String(200), nullable=False)
    external_customer_id = Column(String(200))

    order_number = Column(String(100))
    status = Column(String(100))                        # pending | processing | completed | cancelled …
    total_amount = Column(Numeric(12, 2), default=0)
    currency = Column(String(10), default="USD")
    payment_status = Column(String(100))
    payment_method = Column(String(200))
    shipping_address = Column(JSON, default=dict)
    notes = Column(Text)

    ordered_at = Column(DateTime(timezone=True))
    shipped_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))

    raw_data = Column(JSON, default=dict)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_order_source_external"),
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_ordered_at", "ordered_at"),
    )

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
#  Order Items
# ─────────────────────────────────────────────────────────────────────────────

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(200))

    product_id = Column(String(200))
    product_name = Column(String(500))
    sku = Column(String(200))
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)
    discount = Column(Numeric(12, 2), default=0)
    category = Column(String(300))

    raw_data = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_sku", "sku"),
    )

    order = relationship("Order", back_populates="items")


# ─────────────────────────────────────────────────────────────────────────────
#  Sync Jobs  (audit trail)
# ─────────────────────────────────────────────────────────────────────────────

class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    triggered_by = Column(
        Enum("cron", "manual", name="sync_trigger_enum"), default="cron"
    )
    status = Column(
        Enum("running", "completed", "failed", name="sync_status_enum"), default="running"
    )
    customers_synced = Column(Integer, default=0)
    orders_synced = Column(Integer, default=0)
    items_synced = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))

    data_source = relationship("DataSource", back_populates="sync_jobs")


# ─────────────────────────────────────────────────────────────────────────────
#  Query Cache  (semantic NL→SQL vector store)
# ─────────────────────────────────────────────────────────────────────────────

class QueryCache(Base):
    """
    Stores successful NL→SQL pairs with their embeddings.
    On each new query the embedding is compared against this table first.
    If similarity > threshold the cached SQL is reused without any LLM call.
    """
    __tablename__ = "query_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    natural_language = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    embedding = Column(Vector(1536))                    # text-embedding-3-small dim
    usage_count = Column(Integer, default=1)
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_query_cache_embedding", "embedding", postgresql_using="ivfflat",
              postgresql_with={"lists": "100"}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Query Sessions  (conversation threads)
# ─────────────────────────────────────────────────────────────────────────────

class QuerySession(Base):
    __tablename__ = "query_sessions"

    id = Column(String(100), primary_key=True)          # passed by caller (thread/session id)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    logs = relationship("QueryLog", back_populates="session", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
#  Query Logs  (every NL2SQL request)
# ─────────────────────────────────────────────────────────────────────────────

class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), ForeignKey("query_sessions.id", ondelete="SET NULL"), nullable=True)

    user_question = Column(Text, nullable=False)
    reframed_question = Column(Text)
    generated_sql = Column(Text)
    sql_source = Column(
        Enum("vector_cache", "llm", name="sql_source_enum"), default="llm"
    )
    result_rows = Column(Integer, default=0)
    nl_response = Column(Text)
    error = Column(Text)
    retry_count = Column(Integer, default=0)

    # Token usage
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # Timing
    total_latency_ms = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_query_logs_session_id", "session_id"),
        Index("ix_query_logs_created_at", "created_at"),
    )

    session = relationship("QuerySession", back_populates="logs")
