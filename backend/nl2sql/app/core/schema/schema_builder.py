"""
app/core/schema/schema_builder.py
──────────────────────────────────
Builds LLM-facing schema strings for the e-commerce database.

Two modes:
  • narrow_schema(tables) — only the tables relevant to the question
  • full_schema()         — all tables
"""

from typing import Iterable, List

SCHEMA_MAP = {
    "customers": """
Table: customers
Description: Registered customers and their account profile.
Columns:
  - customer_id UUID primary key
  - first_name VARCHAR
  - last_name VARCHAR
  - email VARCHAR unique
  - phone VARCHAR unique
  - password_hash TEXT sensitive, never select
  - gender VARCHAR
  - date_of_birth DATE
  - is_email_verified BOOLEAN
  - is_phone_verified BOOLEAN
  - status VARCHAR
  - created_at TIMESTAMP
  - updated_at TIMESTAMP
""",
    "customer_addresses": """
Table: customer_addresses
Description: Multiple shipping or billing addresses for each customer.
Columns:
  - address_id UUID primary key
  - customer_id UUID fk to customers.customer_id
  - full_name VARCHAR
  - phone VARCHAR
  - address_line1 TEXT
  - address_line2 TEXT
  - landmark TEXT
  - city VARCHAR
  - state VARCHAR
  - country VARCHAR
  - postal_code VARCHAR
  - address_type VARCHAR
  - is_default BOOLEAN
  - created_at TIMESTAMP
""",
    "categories": """
Table: categories
Description: Product categories with parent-child hierarchy.
Columns:
  - category_id UUID primary key
  - parent_category_id UUID fk to categories.category_id
  - category_name VARCHAR
  - slug VARCHAR unique
  - created_at TIMESTAMP
""",
    "sellers": """
Table: sellers
Description: Marketplace vendors or merchants selling products.
Columns:
  - seller_id UUID primary key
  - business_name VARCHAR
  - seller_name VARCHAR
  - email VARCHAR
  - phone VARCHAR
  - gst_number VARCHAR
  - rating NUMERIC(3,2)
  - created_at TIMESTAMP
""",
    "products": """
Table: products
Description: Core product catalog information.
Columns:
  - product_id UUID primary key
  - seller_id UUID fk to sellers.seller_id
  - category_id UUID fk to categories.category_id
  - product_name VARCHAR
  - slug VARCHAR unique
  - short_description TEXT
  - description TEXT
  - brand VARCHAR
  - status VARCHAR
  - created_at TIMESTAMP
  - updated_at TIMESTAMP
""",
    "product_variants": """
Table: product_variants
Description: Sellable variants for each product such as color, size, storage, or RAM.
Columns:
  - variant_id UUID primary key
  - product_id UUID fk to products.product_id
  - sku VARCHAR unique
  - variant_name VARCHAR
  - color VARCHAR
  - size VARCHAR
  - price NUMERIC(12,2)
  - discount_price NUMERIC(12,2)
  - currency VARCHAR
  - weight NUMERIC(10,2)
  - stock_quantity INTEGER
  - status VARCHAR
  - created_at TIMESTAMP
""",
    "product_images": """
Table: product_images
Description: Product and variant image URLs.
Columns:
  - image_id UUID primary key
  - product_id UUID fk to products.product_id
  - variant_id UUID fk to product_variants.variant_id
  - image_url TEXT
  - is_primary BOOLEAN
  - sort_order INTEGER
""",
    "attributes": """
Table: attributes
Description: Dynamic attribute names such as RAM, material, sleeve, storage, or fabric.
Columns:
  - attribute_id UUID primary key
  - attribute_name VARCHAR
""",
    "product_attribute_values": """
Table: product_attribute_values
Description: Attribute values attached to products or variants.
Columns:
  - id UUID primary key
  - product_id UUID fk to products.product_id
  - variant_id UUID fk to product_variants.variant_id
  - attribute_id UUID fk to attributes.attribute_id
  - attribute_value VARCHAR
""",
    "carts": """
Table: carts
Description: Customer shopping carts.
Columns:
  - cart_id UUID primary key
  - customer_id UUID fk to customers.customer_id
  - created_at TIMESTAMP
""",
    "cart_items": """
Table: cart_items
Description: Items currently in a customer's cart.
Columns:
  - cart_item_id UUID primary key
  - cart_id UUID fk to carts.cart_id
  - variant_id UUID fk to product_variants.variant_id
  - quantity INTEGER
  - created_at TIMESTAMP
""",
    "orders": """
Table: orders
Description: Customer order headers.
Columns:
  - order_id UUID primary key
  - customer_id UUID fk to customers.customer_id
  - order_number VARCHAR unique
  - address_id UUID fk to customer_addresses.address_id
  - order_status VARCHAR
  - subtotal NUMERIC(12,2)
  - tax_amount NUMERIC(12,2)
  - shipping_amount NUMERIC(12,2)
  - discount_amount NUMERIC(12,2)
  - total_amount NUMERIC(12,2)
  - payment_status VARCHAR
  - placed_at TIMESTAMP
""",
    "order_items": """
Table: order_items
Description: Snapshot of product and variant sold in an order.
Columns:
  - order_item_id UUID primary key
  - order_id UUID fk to orders.order_id
  - product_id UUID
  - variant_id UUID
  - product_name VARCHAR
  - variant_name VARCHAR
  - sku VARCHAR
  - unit_price NUMERIC(12,2)
  - quantity INTEGER
  - total_price NUMERIC(12,2)
""",
    "payments": """
Table: payments
Description: Payment transactions for orders.
Columns:
  - payment_id UUID primary key
  - order_id UUID fk to orders.order_id
  - payment_method VARCHAR
  - transaction_id VARCHAR
  - payment_gateway VARCHAR
  - payment_status VARCHAR
  - paid_amount NUMERIC(12,2)
  - paid_at TIMESTAMP
""",
    "shipments": """
Table: shipments
Description: Shipping and delivery tracking for orders.
Columns:
  - shipment_id UUID primary key
  - order_id UUID fk to orders.order_id
  - courier_name VARCHAR
  - tracking_number VARCHAR
  - shipping_status VARCHAR
  - shipped_at TIMESTAMP
  - delivered_at TIMESTAMP
""",
    "product_reviews": """
Table: product_reviews
Description: Customer reviews and ratings for products.
Columns:
  - review_id UUID primary key
  - product_id UUID fk to products.product_id
  - customer_id UUID fk to customers.customer_id
  - rating INTEGER between 1 and 5
  - review_title VARCHAR
  - review_text TEXT
  - created_at TIMESTAMP
""",
    "wishlists": """
Table: wishlists
Description: Customer wishlisted variants.
Columns:
  - wishlist_id UUID primary key
  - customer_id UUID fk to customers.customer_id
  - variant_id UUID fk to product_variants.variant_id
  - created_at TIMESTAMP
""",
    "coupons": """
Table: coupons
Description: Discount offers and promotional codes.
Columns:
  - coupon_id UUID primary key
  - code VARCHAR unique
  - discount_type VARCHAR
  - discount_value NUMERIC(12,2)
  - min_order_amount NUMERIC(12,2)
  - max_discount_amount NUMERIC(12,2)
  - valid_from TIMESTAMP
  - valid_to TIMESTAMP
  - usage_limit INTEGER
  - created_at TIMESTAMP
""",
}


ENTITY_TAG_DICTIONARY = {
    "customers": ["customer", "buyer", "shopper", "account", "user", "member", "client"],
    "customer_addresses": ["address", "shipping address", "billing address", "city", "state", "country", "postal code"],
    "categories": ["category", "department", "catalog section", "subcategory"],
    "sellers": ["seller", "vendor", "merchant", "store", "shop"],
    "products": ["product", "item", "catalog", "brand", "listing"],
    "product_variants": ["variant", "sku", "color", "size", "storage", "ram", "stock", "inventory"],
    "product_images": ["image", "photo", "gallery", "thumbnail"],
    "attributes": ["attribute", "specification", "property", "feature name"],
    "product_attribute_values": ["attribute value", "spec", "feature value", "material", "fabric"],
    "carts": ["cart", "basket", "shopping cart"],
    "cart_items": ["cart item", "basket item", "items in cart"],
    "orders": ["order", "purchase", "transaction", "checkout", "invoice"],
    "order_items": ["order item", "line item", "ordered product", "units sold"],
    "payments": ["payment", "transaction id", "gateway", "paid amount", "payment method"],
    "shipments": ["shipment", "delivery", "tracking", "courier", "shipping"],
    "product_reviews": ["review", "rating", "feedback", "stars"],
    "wishlists": ["wishlist", "saved item", "favourites", "favorite"],
    "coupons": ["coupon", "promo", "discount code", "offer", "voucher"],
}


DEPENDENCY_MAP = {
    "customer_addresses": {"customers"},
    "products": {"categories", "sellers"},
    "product_variants": {"products"},
    "product_images": {"products", "product_variants"},
    "product_attribute_values": {"products", "product_variants", "attributes"},
    "carts": {"customers"},
    "cart_items": {"carts", "product_variants"},
    "orders": {"customers", "customer_addresses"},
    "order_items": {"orders"},
    "payments": {"orders"},
    "shipments": {"orders"},
    "product_reviews": {"products", "customers"},
    "wishlists": {"customers", "product_variants"},
}


JOIN_GUIDANCE = """
Join guidance:
  - customer_addresses.customer_id = customers.customer_id
  - carts.customer_id = customers.customer_id
  - cart_items.cart_id = carts.cart_id
  - cart_items.variant_id = product_variants.variant_id
  - products.seller_id = sellers.seller_id
  - products.category_id = categories.category_id
  - product_variants.product_id = products.product_id
  - product_images.product_id = products.product_id
  - product_images.variant_id = product_variants.variant_id
  - product_attribute_values.product_id = products.product_id
  - product_attribute_values.variant_id = product_variants.variant_id
  - product_attribute_values.attribute_id = attributes.attribute_id
  - orders.customer_id = customers.customer_id
  - orders.address_id = customer_addresses.address_id
  - order_items.order_id = orders.order_id
  - payments.order_id = orders.order_id
  - shipments.order_id = orders.order_id
  - product_reviews.product_id = products.product_id
  - product_reviews.customer_id = customers.customer_id
  - wishlists.customer_id = customers.customer_id
  - wishlists.variant_id = product_variants.variant_id
"""


TABLE_ORDER = list(SCHEMA_MAP.keys())


def _expand_dependencies(selected: Iterable[str]) -> List[str]:
    expanded = set(selected)
    changed = True
    while changed:
        changed = False
        for table in list(expanded):
            for dep in DEPENDENCY_MAP.get(table, set()):
                if dep not in expanded:
                    expanded.add(dep)
                    changed = True
    return [table for table in TABLE_ORDER if table in expanded]


def narrow_schema(tables: List[str]) -> str:
    selected = _expand_dependencies(tables or ["customers", "orders", "order_items"])
    blocks = [SCHEMA_MAP[table] for table in selected if table in SCHEMA_MAP]
    if len(selected) > 1:
        blocks.append(JOIN_GUIDANCE)
    return "\n".join(blocks)


def full_schema() -> str:
    return "\n".join(SCHEMA_MAP[table] for table in TABLE_ORDER) + "\n" + JOIN_GUIDANCE
