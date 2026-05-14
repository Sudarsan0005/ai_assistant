"""Initial schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── data_sources ────────────────────────────────────────────────────────
    op.create_table(
        'data_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('db_type', sa.Enum('postgresql', 'mysql', 'mssql', 'sqlite', name='db_type_enum'), nullable=False, server_default='postgresql'),
        sa.Column('host', sa.String(500), nullable=False),
        sa.Column('port', sa.Integer, nullable=False),
        sa.Column('database_name', sa.String(200), nullable=False),
        sa.Column('username', sa.String(200), nullable=False),
        sa.Column('password_encrypted', sa.Text, nullable=False),
        sa.Column('schema_name', sa.String(100), server_default='public'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('table_mapping', postgresql.JSON, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # ── customers ────────────────────────────────────────────────────────────
    op.create_table(
        'customers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.String(200), nullable=False),
        sa.Column('first_name', sa.String(200)),
        sa.Column('last_name', sa.String(200)),
        sa.Column('email', sa.String(500)),
        sa.Column('phone', sa.String(100)),
        sa.Column('company', sa.String(300)),
        sa.Column('city', sa.String(200)),
        sa.Column('state', sa.String(200)),
        sa.Column('country', sa.String(200)),
        sa.Column('postal_code', sa.String(50)),
        sa.Column('status', sa.String(100)),
        sa.Column('customer_since', sa.DateTime(timezone=True)),
        sa.Column('lifetime_value', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total_orders', sa.Integer, server_default='0'),
        sa.Column('raw_data', postgresql.JSON, server_default='{}'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_customer_source_external'),
    )
    op.create_index('ix_customers_email', 'customers', ['email'])
    op.create_index('ix_customers_source_id', 'customers', ['source_id'])
    op.create_index('ix_customers_status', 'customers', ['status'])

    # ── orders ───────────────────────────────────────────────────────────────
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('external_id', sa.String(200), nullable=False),
        sa.Column('external_customer_id', sa.String(200)),
        sa.Column('order_number', sa.String(100)),
        sa.Column('status', sa.String(100)),
        sa.Column('total_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('payment_status', sa.String(100)),
        sa.Column('payment_method', sa.String(200)),
        sa.Column('shipping_address', postgresql.JSON, server_default='{}'),
        sa.Column('notes', sa.Text),
        sa.Column('ordered_at', sa.DateTime(timezone=True)),
        sa.Column('shipped_at', sa.DateTime(timezone=True)),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.Column('raw_data', postgresql.JSON, server_default='{}'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_order_source_external'),
    )
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_orders_ordered_at', 'orders', ['ordered_at'])

    # ── order_items ──────────────────────────────────────────────────────────
    op.create_table(
        'order_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.String(200)),
        sa.Column('product_id', sa.String(200)),
        sa.Column('product_name', sa.String(500)),
        sa.Column('sku', sa.String(200)),
        sa.Column('quantity', sa.Integer, server_default='1'),
        sa.Column('unit_price', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total_price', sa.Numeric(12, 2), server_default='0'),
        sa.Column('discount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('category', sa.String(300)),
        sa.Column('raw_data', postgresql.JSON, server_default='{}'),
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])
    op.create_index('ix_order_items_sku', 'order_items', ['sku'])

    # ── sync_jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        'sync_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('triggered_by', sa.Enum('cron', 'manual', name='sync_trigger_enum'), server_default='cron'),
        sa.Column('status', sa.Enum('running', 'completed', 'failed', name='sync_status_enum'), server_default='running'),
        sa.Column('customers_synced', sa.Integer, server_default='0'),
        sa.Column('orders_synced', sa.Integer, server_default='0'),
        sa.Column('items_synced', sa.Integer, server_default='0'),
        sa.Column('error_message', sa.Text),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
    )

    # ── query_sessions ───────────────────────────────────────────────────────
    op.create_table(
        'query_sessions',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── query_cache (vector store) ───────────────────────────────────────────
    op.create_table(
        'query_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('natural_language', sa.Text, nullable=False),
        sa.Column('sql_query', sa.Text, nullable=False),
        sa.Column('embedding', sa.Text),   # stored as vector via raw SQL
        sa.Column('usage_count', sa.Integer, server_default='1'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Convert embedding column to vector type after table creation
    op.execute("ALTER TABLE query_cache ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.execute("CREATE INDEX ix_query_cache_embedding ON query_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    # ── query_logs ───────────────────────────────────────────────────────────
    op.create_table(
        'query_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', sa.String(100), sa.ForeignKey('query_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_question', sa.Text, nullable=False),
        sa.Column('reframed_question', sa.Text),
        sa.Column('generated_sql', sa.Text),
        sa.Column('sql_source', sa.Enum('vector_cache', 'llm', name='sql_source_enum'), server_default='llm'),
        sa.Column('result_rows', sa.Integer, server_default='0'),
        sa.Column('nl_response', sa.Text),
        sa.Column('error', sa.Text),
        sa.Column('retry_count', sa.Integer, server_default='0'),
        sa.Column('input_tokens', sa.Integer, server_default='0'),
        sa.Column('output_tokens', sa.Integer, server_default='0'),
        sa.Column('total_tokens', sa.Integer, server_default='0'),
        sa.Column('total_latency_ms', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_query_logs_session_id', 'query_logs', ['session_id'])
    op.create_index('ix_query_logs_created_at', 'query_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('query_logs')
    op.drop_table('query_cache')
    op.drop_table('query_sessions')
    op.drop_table('sync_jobs')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('customers')
    op.drop_table('data_sources')
    op.execute("DROP TYPE IF EXISTS db_type_enum")
    op.execute("DROP TYPE IF EXISTS sync_trigger_enum")
    op.execute("DROP TYPE IF EXISTS sync_status_enum")
    op.execute("DROP TYPE IF EXISTS sql_source_enum")
