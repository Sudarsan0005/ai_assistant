"""
scripts/seed_sample_data.py
────────────────────────────────────────────────────────────────────────────
Inserts a realistic set of sample customers, orders, and order items
into the internal database so you can test NL2SQL queries immediately
without connecting to an external source.

Run: python scripts/seed_sample_data.py
"""

import random
import sys
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.connection import init_db, db_session
from app.models.tables import Customer, DataSource, Order, OrderItem
from app.utils.encryption import encrypt_password

# ─────────────────────────────────────────────────────────────────────────────

PRODUCTS = [
    ("Premium Headphones", "HDPH-PRO-BLK", "Electronics", 149.99),
    ("Wireless Mouse", "MOUSE-WL-GRY", "Electronics", 39.99),
    ("Standing Desk Mat", "MAT-DESK-BRN", "Office", 59.99),
    ("Python Crash Course", "BOOK-PY-001", "Books", 29.99),
    ("Coffee Subscription", "COFFEE-SUB-M", "Food & Drink", 24.99),
    ("Yoga Mat", "YOGA-MAT-PRP", "Sports", 34.99),
    ("Blue T-Shirt (M)", "SHIRT-BLU-M", "Apparel", 19.99),
    ("Running Shoes", "SHOES-RUN-42", "Sports", 89.99),
    ("USB-C Hub", "HUB-USBC-7P", "Electronics", 49.99),
    ("Notebook (A5)", "NB-A5-LND", "Stationery", 12.99),
]

STATUSES = ["active", "active", "active", "vip", "inactive", "vip"]
ORDER_STATUSES = ["completed", "completed", "completed", "processing", "pending", "cancelled", "refunded"]
PAYMENT_METHODS = ["credit_card", "paypal", "bank_transfer", "stripe"]
COUNTRIES = ["USA", "UK", "Canada", "Australia", "Germany", "France"]
CITIES = ["New York", "London", "Toronto", "Sydney", "Berlin", "Paris", "Chicago", "Austin"]

FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
               "Isabella", "James", "Kate", "Liam", "Mia", "Noah", "Olivia", "Peter"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White"]


def random_date(days_back: int) -> datetime:
    delta = random.randint(0, days_back)
    return datetime.now(timezone.utc) - timedelta(days=delta)


def make_order_items(order: Order, count: int) -> list[OrderItem]:
    items = []
    chosen = random.sample(PRODUCTS, min(count, len(PRODUCTS)))
    for product_name, sku, category, unit_price in chosen:
        qty = random.randint(1, 4)
        discount = round(random.choice([0, 0, 0, 5.0, 10.0]), 2)
        items.append(OrderItem(
            order_id=order.id,
            product_name=product_name,
            sku=sku,
            category=category,
            quantity=qty,
            unit_price=Decimal(str(unit_price)),
            total_price=Decimal(str(round(unit_price * qty - discount, 2))),
            discount=Decimal(str(discount)),
        ))
    return items


def seed():
    init_db()

    with db_session() as db:
        existing_customers = db.query(Customer).count()
        existing_orders = db.query(Order).count()
        existing_items = db.query(OrderItem).count()

        if existing_customers or existing_orders or existing_items:
            print(
                "ℹ️ Sample data already present — skipping seed "
                f"(customers={existing_customers}, orders={existing_orders}, items={existing_items})."
            )
            return

        # ── Create a dummy data source ────────────────────────────────────────
        source = DataSource(
            name="Sample Store",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database_name="sample_store",
            username="demo",
            password_encrypted=encrypt_password("demo_password"),
            schema_name="public",
            table_mapping={},
        )
        db.add(source)
        db.flush()

        customers = []
        for i in range(40):
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            status = random.choice(STATUSES)
            since = random_date(730)
            c = Customer(
                source_id=source.id,
                external_id=f"EXT-C-{i+1:04d}",
                first_name=fn,
                last_name=ln,
                email=f"{fn.lower()}.{ln.lower()}{i}@example.com",
                phone=f"+1-555-{random.randint(1000,9999)}",
                company=random.choice(["Acme Corp", "TechCo", "Startup Inc", None, None]),
                city=random.choice(CITIES),
                country=random.choice(COUNTRIES),
                status=status,
                customer_since=since,
                total_orders=0,
                lifetime_value=Decimal("0.00"),
            )
            db.add(c)
            db.flush()
            customers.append(c)

        # ── Create orders for customers ───────────────────────────────────────
        for customer in customers:
            order_count = random.randint(1, 8)
            total_ltv = Decimal("0.00")

            for j in range(order_count):
                order_status = random.choice(ORDER_STATUSES)
                ordered_at = random_date(365)
                total = Decimal(str(round(random.uniform(20, 400), 2)))

                order = Order(
                    source_id=source.id,
                    customer_id=customer.id,
                    external_id=f"EXT-O-{customer.external_id}-{j+1}",
                    order_number=f"ORD-{random.randint(10000,99999)}",
                    status=order_status,
                    total_amount=total,
                    currency="USD",
                    payment_status="paid" if order_status == "completed" else "pending",
                    payment_method=random.choice(PAYMENT_METHODS),
                    ordered_at=ordered_at,
                    shipped_at=ordered_at + timedelta(days=2) if order_status in ("completed", "processing") else None,
                    delivered_at=ordered_at + timedelta(days=5) if order_status == "completed" else None,
                )
                db.add(order)
                db.flush()

                items = make_order_items(order, random.randint(1, 4))
                for item in items:
                    db.add(item)

                if order_status == "completed":
                    total_ltv += total

            customer.total_orders = order_count
            customer.lifetime_value = total_ltv

        print(f"✅ Seeded {len(customers)} customers with their orders and items.")
        print("You can now run NL queries like:")
        print('  POST /query { "question": "Show me all VIP customers" }')
        print('  POST /query { "question": "What is the total revenue from completed orders?" }')
        print('  POST /query { "question": "List the top 5 customers by lifetime value" }')


if __name__ == "__main__":
    seed()
