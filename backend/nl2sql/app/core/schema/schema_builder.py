"""
app/core/schema/schema_builder.py
──────────────────────────────────
Builds the SQL schema string that gets injected into LLM prompts.

Two modes:
  • narrow_schema(entities)  — only the tables relevant to the question
  • full_schema()            — all tables (used on retry)

The schema string format is human-readable CREATE TABLE style with
column descriptions inline, which is the most reliable format for
LLM SQL generation (better than JSON or raw DDL).
"""

from typing import List

CUSTOMER_SCHEMA = """
Table: customers
Description: Synced customer profiles from the source database.
Columns:
  - id               UUID        Primary key (internal)
  - external_id      VARCHAR     Original ID in source system
  - first_name       VARCHAR     Customer first name
  - last_name        VARCHAR     Customer last name
  - email            VARCHAR     Customer email address (use ILIKE for search)
  - phone            VARCHAR     Phone number
  - company          VARCHAR     Company name the customer belongs to
  - city             VARCHAR     Customer city
  - state            VARCHAR     Customer state/province
  - country          VARCHAR     Customer country
  - postal_code      VARCHAR     ZIP/postal code
  - status           VARCHAR     Account status: 'active', 'inactive', 'vip', 'blocked'
  - customer_since   TIMESTAMP   When the customer first registered
  - lifetime_value   NUMERIC     Total amount spent by this customer
  - total_orders     INTEGER     Total number of orders placed

Key relationships:
  - customers.id → orders.customer_id (one customer has many orders)
"""

ORDER_SCHEMA = """
Table: orders
Description: Synced order records. Each row is one order placed by a customer.
Columns:
  - id                   UUID        Primary key (internal)
  - customer_id          UUID        FK to customers.id
  - external_id          VARCHAR     Original order ID in source system
  - order_number         VARCHAR     Human-readable order number (e.g. ORD-1001)
  - status               VARCHAR     Order status: 'pending','processing','completed','cancelled','refunded'
  - total_amount         NUMERIC     Total order value including tax/shipping
  - currency             VARCHAR     Currency code, e.g. 'USD', 'EUR'
  - payment_status       VARCHAR     'paid', 'pending', 'failed', 'refunded'
  - payment_method       VARCHAR     e.g. 'credit_card', 'paypal', 'bank_transfer'
  - shipping_address     JSONB       Shipping address as JSON object
  - notes                TEXT        Order notes or comments
  - ordered_at           TIMESTAMP   When the order was placed
  - shipped_at           TIMESTAMP   When the order was shipped (NULL if not yet shipped)
  - delivered_at         TIMESTAMP   When the order was delivered (NULL if not yet delivered)

Key relationships:
  - orders.customer_id → customers.id
  - orders.id → order_items.order_id (one order has many items)
"""

ORDER_ITEM_SCHEMA = """
Table: order_items
Description: Line items (individual products) within each order.
Columns:
  - id              UUID        Primary key
  - order_id        UUID        FK to orders.id
  - product_id      VARCHAR     Product identifier
  - product_name    VARCHAR     Full product name
  - sku             VARCHAR     Stock keeping unit code
  - quantity        INTEGER     Quantity ordered
  - unit_price      NUMERIC     Price per unit
  - total_price     NUMERIC     quantity × unit_price
  - discount        NUMERIC     Discount applied to this line item
  - category        VARCHAR     Product category

Key relationships:
  - order_items.order_id → orders.id
"""

# Map entity names to their schema blocks
SCHEMA_MAP = {
    "customers": CUSTOMER_SCHEMA,
    "orders": ORDER_SCHEMA,
    "order_items": ORDER_ITEM_SCHEMA,
}

# Pre-built join guidance appended when multiple tables are present
JOIN_GUIDANCE = """
Join guidance:
  - customers ↔ orders:      JOIN orders o ON o.customer_id = c.id
  - orders ↔ order_items:    JOIN order_items oi ON oi.order_id = o.id
  - three-table join example:
      FROM customers c
      JOIN orders o ON o.customer_id = c.id
      JOIN order_items oi ON oi.order_id = o.id
"""


def narrow_schema(entities: List[str]) -> str:
    """
    Return only the schema blocks for the given entity list.
    Always includes customers if orders or order_items are present,
    because joins almost always require the customers table.
    """
    selected = set(entities)

    # Ensure customers is always available when orders are queried
    if "orders" in selected or "order_items" in selected:
        selected.add("customers")

    # Ensure orders is available when order_items is queried
    if "order_items" in selected:
        selected.add("orders")

    blocks = [SCHEMA_MAP[e] for e in ["customers", "orders", "order_items"] if e in selected]

    if len(selected) > 1:
        blocks.append(JOIN_GUIDANCE)

    return "\n".join(blocks)


def full_schema() -> str:
    """Return the complete schema for all tables (used on retry)."""
    return "\n".join(list(SCHEMA_MAP.values())) + "\n" + JOIN_GUIDANCE
