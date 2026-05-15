"""Initial e-commerce schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "customers",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(20), unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("gender", sa.String(20)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("is_email_verified", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("is_phone_verified", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "categories",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parent_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.category_id", ondelete="SET NULL")),
        sa.Column("category_name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sellers",
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("business_name", sa.String(255)),
        sa.Column("seller_name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20)),
        sa.Column("gst_number", sa.String(50)),
        sa.Column("rating", sa.Numeric(3, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "attributes",
        sa.Column("attribute_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("attribute_name", sa.String(100), nullable=False),
    )

    op.create_table(
        "customer_addresses",
        sa.Column("address_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(150)),
        sa.Column("phone", sa.String(20)),
        sa.Column("address_line1", sa.Text()),
        sa.Column("address_line2", sa.Text()),
        sa.Column("landmark", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("address_type", sa.String(20)),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.seller_id", ondelete="SET NULL")),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.category_id", ondelete="SET NULL")),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True),
        sa.Column("short_description", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("brand", sa.String(255)),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "product_variants",
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False, unique=True),
        sa.Column("variant_name", sa.String(255)),
        sa.Column("color", sa.String(100)),
        sa.Column("size", sa.String(100)),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("discount_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10), server_default="INR"),
        sa.Column("weight", sa.Numeric(10, 2)),
        sa.Column("stock_quantity", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "product_images",
        sa.Column("image_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.variant_id", ondelete="SET NULL")),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "product_attribute_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.variant_id", ondelete="CASCADE")),
        sa.Column("attribute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("attributes.attribute_id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribute_value", sa.String(255)),
    )

    op.create_table(
        "carts",
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "cart_items",
        sa.Column("cart_item_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.cart_id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.variant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "orders",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id", ondelete="SET NULL")),
        sa.Column("order_number", sa.String(100), unique=True),
        sa.Column("address_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_addresses.address_id", ondelete="SET NULL")),
        sa.Column("order_status", sa.String(50)),
        sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("tax_amount", sa.Numeric(12, 2)),
        sa.Column("shipping_amount", sa.Numeric(12, 2)),
        sa.Column("discount_amount", sa.Numeric(12, 2)),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("payment_status", sa.String(50)),
        sa.Column("placed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "order_items",
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True)),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True)),
        sa.Column("product_name", sa.String(500)),
        sa.Column("variant_name", sa.String(255)),
        sa.Column("sku", sa.String(100)),
        sa.Column("unit_price", sa.Numeric(12, 2)),
        sa.Column("quantity", sa.Integer()),
        sa.Column("total_price", sa.Numeric(12, 2)),
    )

    op.create_table(
        "payments",
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("transaction_id", sa.String(255)),
        sa.Column("payment_gateway", sa.String(100)),
        sa.Column("payment_status", sa.String(50)),
        sa.Column("paid_amount", sa.Numeric(12, 2)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "shipments",
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False),
        sa.Column("courier_name", sa.String(100)),
        sa.Column("tracking_number", sa.String(255)),
        sa.Column("shipping_status", sa.String(50)),
        sa.Column("shipped_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "product_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id", ondelete="SET NULL")),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_title", sa.String(255)),
        sa.Column("review_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_reviews_rating"),
    )

    op.create_table(
        "wishlists",
        sa.Column("wishlist_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_variants.variant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "coupons",
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("discount_type", sa.String(20)),
        sa.Column("discount_value", sa.Numeric(12, 2)),
        sa.Column("min_order_amount", sa.Numeric(12, 2)),
        sa.Column("max_discount_amount", sa.Numeric(12, 2)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("usage_limit", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "query_sessions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "query_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("natural_language", sa.Text(), nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text()),
        sa.Column("usage_count", sa.Integer(), server_default="1"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE query_cache ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.execute("CREATE INDEX ix_query_cache_embedding ON query_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    op.create_table(
        "query_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(100), sa.ForeignKey("query_sessions.id", ondelete="SET NULL")),
        sa.Column("user_question", sa.Text(), nullable=False),
        sa.Column("reframed_question", sa.Text()),
        sa.Column("generated_sql", sa.Text()),
        sa.Column("sql_source", sa.String(32), server_default="llm"),
        sa.Column("result_rows", sa.Integer(), server_default="0"),
        sa.Column("nl_response", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("input_tokens", sa.Integer(), server_default="0"),
        sa.Column("output_tokens", sa.Integer(), server_default="0"),
        sa.Column("total_tokens", sa.Integer(), server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "query_logs",
        "query_cache",
        "query_sessions",
        "coupons",
        "wishlists",
        "product_reviews",
        "shipments",
        "payments",
        "order_items",
        "orders",
        "cart_items",
        "carts",
        "product_attribute_values",
        "product_images",
        "product_variants",
        "products",
        "customer_addresses",
        "attributes",
        "sellers",
        "categories",
        "customers",
    ]:
        op.drop_table(table)
