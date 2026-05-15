"""
app/models/tables.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy ORM models for the internal e-commerce analytics database.

Business tables:
  • customers
  • customer_addresses
  • categories
  • sellers
  • products
  • product_variants
  • product_images
  • attributes
  • product_attribute_values
  • carts
  • cart_items
  • orders
  • order_items
  • payments
  • shipments
  • product_reviews
  • wishlists
  • coupons

NL2SQL support tables:
  • query_cache
  • query_sessions
  • query_logs
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20), unique=True)
    password_hash = Column(Text, nullable=False)
    gender = Column(String(20))
    date_of_birth = Column(Date)
    is_email_verified = Column(Boolean, default=False)
    is_phone_verified = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    carts = relationship("Cart", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    reviews = relationship("ProductReview", back_populates="customer")
    wishlists = relationship("Wishlist", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_customers_email", "email"),
        Index("ix_customers_status", "status"),
        Index("ix_customers_created_at", "created_at"),
    )


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    address_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(150))
    phone = Column(String(20))
    address_line1 = Column(Text)
    address_line2 = Column(Text)
    landmark = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))
    address_type = Column(String(20))
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="addresses")
    orders = relationship("Order", back_populates="address")

    __table_args__ = (
        Index("ix_customer_addresses_customer_id", "customer_id"),
        Index("ix_customer_addresses_city", "city"),
        Index("ix_customer_addresses_country", "country"),
    )


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_category_id = Column(UUID(as_uuid=True), ForeignKey("categories.category_id", ondelete="SET NULL"))
    category_name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("Category", remote_side=[category_id], backref="children")
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        Index("ix_categories_parent_category_id", "parent_category_id"),
        Index("ix_categories_category_name", "category_name"),
    )


class Seller(Base):
    __tablename__ = "sellers"

    seller_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name = Column(String(255))
    seller_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(20))
    gst_number = Column(String(50))
    rating = Column(Numeric(3, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    products = relationship("Product", back_populates="seller")

    __table_args__ = (
        Index("ix_sellers_email", "email"),
        Index("ix_sellers_rating", "rating"),
    )


class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.seller_id", ondelete="SET NULL"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.category_id", ondelete="SET NULL"))
    product_name = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True)
    short_description = Column(Text)
    description = Column(Text)
    brand = Column(String(255))
    status = Column(String(30), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    seller = relationship("Seller", back_populates="products")
    category = relationship("Category", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    attribute_values = relationship("ProductAttributeValue", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("ProductReview", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_products_seller_id", "seller_id"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_brand", "brand"),
        Index("ix_products_status", "status"),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    variant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(100), unique=True, nullable=False)
    variant_name = Column(String(255))
    color = Column(String(100))
    size = Column(String(100))
    price = Column(Numeric(12, 2))
    discount_price = Column(Numeric(12, 2))
    currency = Column(String(10), default="INR")
    weight = Column(Numeric(10, 2))
    stock_quantity = Column(Integer, default=0)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="variants")
    images = relationship("ProductImage", back_populates="variant")
    attribute_values = relationship("ProductAttributeValue", back_populates="variant")
    cart_items = relationship("CartItem", back_populates="variant")
    wishlist_items = relationship("Wishlist", back_populates="variant")

    __table_args__ = (
        Index("ix_product_variants_product_id", "product_id"),
        Index("ix_product_variants_status", "status"),
        Index("ix_product_variants_stock_quantity", "stock_quantity"),
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.variant_id", ondelete="SET NULL"))
    image_url = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    product = relationship("Product", back_populates="images")
    variant = relationship("ProductVariant", back_populates="images")

    __table_args__ = (
        Index("ix_product_images_product_id", "product_id"),
        Index("ix_product_images_variant_id", "variant_id"),
    )


class Attribute(Base):
    __tablename__ = "attributes"

    attribute_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attribute_name = Column(String(100), nullable=False)

    values = relationship("ProductAttributeValue", back_populates="attribute")

    __table_args__ = (
        Index("ix_attributes_attribute_name", "attribute_name"),
    )


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.variant_id", ondelete="CASCADE"))
    attribute_id = Column(UUID(as_uuid=True), ForeignKey("attributes.attribute_id", ondelete="CASCADE"), nullable=False)
    attribute_value = Column(String(255))

    product = relationship("Product", back_populates="attribute_values")
    variant = relationship("ProductVariant", back_populates="attribute_values")
    attribute = relationship("Attribute", back_populates="values")

    __table_args__ = (
        Index("ix_product_attribute_values_product_id", "product_id"),
        Index("ix_product_attribute_values_variant_id", "variant_id"),
        Index("ix_product_attribute_values_attribute_id", "attribute_id"),
    )


class Cart(Base):
    __tablename__ = "carts"

    cart_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_carts_customer_id", "customer_id"),
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    cart_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id = Column(UUID(as_uuid=True), ForeignKey("carts.cart_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.variant_id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cart = relationship("Cart", back_populates="items")
    variant = relationship("ProductVariant", back_populates="cart_items")

    __table_args__ = (
        Index("ix_cart_items_cart_id", "cart_id"),
        Index("ix_cart_items_variant_id", "variant_id"),
    )


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="SET NULL"))
    order_number = Column(String(100), unique=True)
    address_id = Column(UUID(as_uuid=True), ForeignKey("customer_addresses.address_id", ondelete="SET NULL"))
    order_status = Column(String(50))
    subtotal = Column(Numeric(12, 2))
    tax_amount = Column(Numeric(12, 2))
    shipping_amount = Column(Numeric(12, 2))
    discount_amount = Column(Numeric(12, 2))
    total_amount = Column(Numeric(12, 2))
    payment_status = Column(String(50))
    placed_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="orders")
    address = relationship("CustomerAddress", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_address_id", "address_id"),
        Index("ix_orders_order_status", "order_status"),
        Index("ix_orders_payment_status", "payment_status"),
        Index("ix_orders_placed_at", "placed_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True))
    variant_id = Column(UUID(as_uuid=True))
    product_name = Column(String(500))
    variant_name = Column(String(255))
    sku = Column(String(100))
    unit_price = Column(Numeric(12, 2))
    quantity = Column(Integer)
    total_price = Column(Numeric(12, 2))

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
        Index("ix_order_items_variant_id", "variant_id"),
        Index("ix_order_items_sku", "sku"),
    )


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    payment_method = Column(String(50))
    transaction_id = Column(String(255))
    payment_gateway = Column(String(100))
    payment_status = Column(String(50))
    paid_amount = Column(Numeric(12, 2))
    paid_at = Column(DateTime(timezone=True))

    order = relationship("Order", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_payment_status", "payment_status"),
        Index("ix_payments_payment_method", "payment_method"),
    )


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    courier_name = Column(String(100))
    tracking_number = Column(String(255))
    shipping_status = Column(String(50))
    shipped_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))

    order = relationship("Order", back_populates="shipments")

    __table_args__ = (
        Index("ix_shipments_order_id", "order_id"),
        Index("ix_shipments_shipping_status", "shipping_status"),
        Index("ix_shipments_tracking_number", "tracking_number"),
    )


class ProductReview(Base):
    __tablename__ = "product_reviews"

    review_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="SET NULL"))
    rating = Column(Integer, nullable=False)
    review_title = Column(String(255))
    review_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="reviews")
    customer = relationship("Customer", back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_reviews_rating"),
        Index("ix_product_reviews_product_id", "product_id"),
        Index("ix_product_reviews_customer_id", "customer_id"),
        Index("ix_product_reviews_rating", "rating"),
    )


class Wishlist(Base):
    __tablename__ = "wishlists"

    wishlist_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.variant_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="wishlists")
    variant = relationship("ProductVariant", back_populates="wishlist_items")

    __table_args__ = (
        Index("ix_wishlists_customer_id", "customer_id"),
        Index("ix_wishlists_variant_id", "variant_id"),
    )


class Coupon(Base):
    __tablename__ = "coupons"

    coupon_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True)
    discount_type = Column(String(20))
    discount_value = Column(Numeric(12, 2))
    min_order_amount = Column(Numeric(12, 2))
    max_discount_amount = Column(Numeric(12, 2))
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    usage_limit = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_coupons_code", "code"),
        Index("ix_coupons_valid_to", "valid_to"),
    )


class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    natural_language = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    usage_count = Column(Integer, default=1)
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_query_cache_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": "100"},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class QuerySession(Base):
    __tablename__ = "query_sessions"

    id = Column(String(100), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    logs = relationship("QueryLog", back_populates="session", cascade="all, delete-orphan")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), ForeignKey("query_sessions.id", ondelete="SET NULL"))
    user_question = Column(Text, nullable=False)
    reframed_question = Column(Text)
    generated_sql = Column(Text)
    sql_source = Column(String(32), default="llm")
    result_rows = Column(Integer, default=0)
    nl_response = Column(Text)
    error = Column(Text)
    retry_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("QuerySession", back_populates="logs")

    __table_args__ = (
        Index("ix_query_logs_session_id", "session_id"),
        Index("ix_query_logs_created_at", "created_at"),
    )
