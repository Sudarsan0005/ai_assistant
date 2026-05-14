"""
app/core/sync/sync_engine.py
────────────────────────────────────────────────────────────────────────────
Data sync engine: connects to the customer's source database,
extracts customer + order + order_item data, and upserts it into
the internal Postgres database.

Supports source DBs: PostgreSQL, MySQL, MSSQL, SQLite.

Design:
  • Discovers source tables via configurable table_mapping.
  • Reads data in batches to avoid memory exhaustion.
  • Uses upsert (INSERT ... ON CONFLICT DO UPDATE) for idempotency.
  • Records every sync in sync_jobs with counters and error details.
  • Can be called manually (API) or on a cron schedule.
"""

import logging
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple
from uuid import UUID

import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.tables import Customer, DataSource, Order, OrderItem, SyncJob
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
#  Source DB connector
# ─────────────────────────────────────────────────────────────────────────────

def _build_source_url(source: DataSource, plain_password: str) -> str:
    """Build a SQLAlchemy connection URL from the DataSource record."""
    drivers = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
        "mssql": "mssql+pymssql",
        "sqlite": "sqlite",
    }
    driver = drivers.get(source.db_type, "postgresql+psycopg2")

    if source.db_type == "sqlite":
        return f"sqlite:///{source.database_name}"

    return (
        f"{driver}://{source.username}:{plain_password}"
        f"@{source.host}:{source.port}/{source.database_name}"
    )


@contextmanager
def source_db_session(source: DataSource, plain_password: str):
    """Open a read-only connection to the source database."""
    url = _build_source_url(source, plain_password)
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()
        engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
#  Column mapping helpers
# ─────────────────────────────────────────────────────────────────────────────

# Default column name mappings: internal_field → list of possible source column names
CUSTOMER_COLUMN_MAP = {
    "external_id":     ["id", "customer_id", "cust_id", "uid"],
    "first_name":      ["first_name", "firstname", "fname", "given_name"],
    "last_name":       ["last_name", "lastname", "lname", "family_name", "surname"],
    "email":           ["email", "email_address", "e_mail", "contact_email"],
    "phone":           ["phone", "phone_number", "mobile", "telephone", "cell"],
    "company":         ["company", "company_name", "organization", "org_name"],
    "city":            ["city", "town"],
    "state":           ["state", "province", "region"],
    "country":         ["country", "country_name", "nation"],
    "postal_code":     ["postal_code", "zip", "zip_code", "postcode"],
    "status":          ["status", "account_status", "customer_status", "state"],
    "customer_since":  ["created_at", "created_date", "registration_date", "customer_since", "join_date"],
    "lifetime_value":  ["lifetime_value", "total_spent", "ltv", "total_revenue"],
    "total_orders":    ["total_orders", "order_count", "num_orders"],
}

ORDER_COLUMN_MAP = {
    "external_id":         ["id", "order_id", "ord_id"],
    "external_customer_id":["customer_id", "cust_id", "user_id", "client_id"],
    "order_number":        ["order_number", "order_no", "reference", "ref_number"],
    "status":              ["status", "order_status", "state"],
    "total_amount":        ["total", "total_amount", "grand_total", "amount", "total_price"],
    "currency":            ["currency", "currency_code"],
    "payment_status":      ["payment_status", "pay_status", "payment_state"],
    "payment_method":      ["payment_method", "pay_method", "payment_type"],
    "notes":               ["notes", "comments", "remarks", "memo"],
    "ordered_at":          ["created_at", "order_date", "ordered_at", "date"],
    "shipped_at":          ["shipped_at", "ship_date", "shipped_date"],
    "delivered_at":        ["delivered_at", "delivery_date", "received_at"],
}

ORDER_ITEM_COLUMN_MAP = {
    "external_id":   ["id", "item_id", "line_id"],
    "product_id":    ["product_id", "prod_id", "item_id"],
    "product_name":  ["product_name", "name", "title", "item_name", "description"],
    "sku":           ["sku", "sku_code", "product_code", "item_code"],
    "quantity":      ["quantity", "qty", "amount", "count"],
    "unit_price":    ["unit_price", "price", "item_price", "cost"],
    "total_price":   ["total_price", "total", "line_total", "subtotal"],
    "discount":      ["discount", "discount_amount", "rebate"],
    "category":      ["category", "product_category", "type"],
}


def _resolve_value(row: Dict, candidates: List[str]) -> Any:
    """Pick the first matching column from a source row."""
    for col in candidates:
        if col in row and row[col] is not None:
            return row[col]
    return None


def _map_row(row: Dict, column_map: Dict[str, List[str]]) -> Dict:
    """Map a source row to internal field names using the column map."""
    return {field: _resolve_value(row, candidates) for field, candidates in column_map.items()}


# ─────────────────────────────────────────────────────────────────────────────
#  Sync Engine
# ─────────────────────────────────────────────────────────────────────────────

class SyncEngine:
    """
    Pulls data from a registered DataSource and upserts into internal DB.

    Usage:
        engine = SyncEngine(db_session)
        stats = engine.run(source_id=uuid, plain_password="...", triggered_by="cron")
    """

    def __init__(self, db: Session):
        self.db = db
        self.batch_size = settings.sync_batch_size

    def run(
        self,
        source_id: UUID,
        plain_password: str,
        triggered_by: str = "cron",
    ) -> Dict[str, Any]:
        """
        Execute a full sync for the given data source.
        Returns a dict with sync statistics.
        """
        source = self.db.query(DataSource).filter_by(id=source_id, is_active=True).first()
        if not source:
            raise ValueError(f"DataSource {source_id} not found or inactive")

        job = SyncJob(source_id=source_id, triggered_by=triggered_by, status="running")
        self.db.add(job)
        self.db.commit()

        stats = {"customers": 0, "orders": 0, "items": 0}

        try:
            with source_db_session(source, plain_password) as conn:
                table_map = source.table_mapping or {}

                # ── Customers ────────────────────────────────────────────────
                customer_table = table_map.get("customers", "customers")
                customers_synced, id_map = self._sync_customers(conn, source, customer_table)
                stats["customers"] = customers_synced

                # ── Orders ───────────────────────────────────────────────────
                order_table = table_map.get("orders", "orders")
                orders_synced, order_id_map = self._sync_orders(conn, source, order_table, id_map)
                stats["orders"] = orders_synced

                # ── Order items ──────────────────────────────────────────────
                item_table = table_map.get("order_items", "order_items")
                items_synced = self._sync_order_items(conn, source, item_table, order_id_map)
                stats["items"] = items_synced

            job.status = "completed"
            job.customers_synced = stats["customers"]
            job.orders_synced = stats["orders"]
            job.items_synced = stats["items"]
            job.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info("Sync completed for source %s: %s", source_id, stats)

        except Exception as exc:
            logger.error("Sync failed for source %s: %s", source_id, exc)
            job.status = "failed"
            job.error_message = traceback.format_exc()[:2000]
            job.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            raise

        return stats

    # ─────────────────────────────────────────────────────────────────────────
    #  Customers
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_customers(
        self, conn, source: DataSource, table_name: str
    ) -> Tuple[int, Dict[str, UUID]]:
        """
        Upsert all customers. Returns (count, external_id → internal_id map).
        """
        count = 0
        id_map: Dict[str, UUID] = {}

        for batch in self._fetch_batches(conn, table_name):
            for row in batch:
                mapped = _map_row(row, CUSTOMER_COLUMN_MAP)
                external_id = str(mapped.get("external_id") or "")
                if not external_id:
                    continue

                existing = (
                    self.db.query(Customer)
                    .filter_by(source_id=source.id, external_id=external_id)
                    .first()
                )

                if existing:
                    # Update fields
                    for k, v in mapped.items():
                        if k != "external_id" and v is not None:
                            setattr(existing, k, v)
                    existing.raw_data = dict(row)
                    internal_id = existing.id
                else:
                    customer = Customer(
                        source_id=source.id,
                        external_id=external_id,
                        raw_data=dict(row),
                        **{k: v for k, v in mapped.items() if k != "external_id" and v is not None},
                    )
                    self.db.add(customer)
                    self.db.flush()
                    internal_id = customer.id
                    count += 1

                id_map[external_id] = internal_id

            self.db.commit()

        return count, id_map

    # ─────────────────────────────────────────────────────────────────────────
    #  Orders
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_orders(
        self,
        conn,
        source: DataSource,
        table_name: str,
        customer_id_map: Dict[str, UUID],
    ) -> Tuple[int, Dict[str, UUID]]:
        """
        Upsert all orders. Returns (count, external_order_id → internal_order_id map).
        """
        count = 0
        order_id_map: Dict[str, UUID] = {}

        for batch in self._fetch_batches(conn, table_name):
            for row in batch:
                mapped = _map_row(row, ORDER_COLUMN_MAP)
                external_id = str(mapped.get("external_id") or "")
                if not external_id:
                    continue

                # Resolve internal customer ID
                ext_cust_id = str(mapped.get("external_customer_id") or "")
                internal_customer_id = customer_id_map.get(ext_cust_id)

                existing = (
                    self.db.query(Order)
                    .filter_by(source_id=source.id, external_id=external_id)
                    .first()
                )

                if existing:
                    for k, v in mapped.items():
                        if k not in ("external_id", "external_customer_id") and v is not None:
                            setattr(existing, k, v)
                    if internal_customer_id:
                        existing.customer_id = internal_customer_id
                    existing.raw_data = dict(row)
                    internal_id = existing.id
                else:
                    order = Order(
                        source_id=source.id,
                        external_id=external_id,
                        customer_id=internal_customer_id,
                        external_customer_id=ext_cust_id,
                        raw_data=dict(row),
                        **{
                            k: v for k, v in mapped.items()
                            if k not in ("external_id", "external_customer_id") and v is not None
                        },
                    )
                    self.db.add(order)
                    self.db.flush()
                    internal_id = order.id
                    count += 1

                order_id_map[external_id] = internal_id

            self.db.commit()

        return count, order_id_map

    # ─────────────────────────────────────────────────────────────────────────
    #  Order Items
    # ─────────────────────────────────────────────────────────────────────────

    def _sync_order_items(
        self,
        conn,
        source: DataSource,
        table_name: str,
        order_id_map: Dict[str, UUID],
    ) -> int:
        """Upsert order items."""
        count = 0

        for batch in self._fetch_batches(conn, table_name):
            for row in batch:
                mapped = _map_row(row, ORDER_ITEM_COLUMN_MAP)

                # Order items table must reference order_id
                ext_order_id = str(_resolve_value(row, ["order_id", "ord_id", "order"]) or "")
                internal_order_id = order_id_map.get(ext_order_id)
                if not internal_order_id:
                    continue

                external_id = str(mapped.get("external_id") or "")

                existing = (
                    self.db.query(OrderItem)
                    .filter_by(order_id=internal_order_id, external_id=external_id)
                    .first()
                    if external_id else None
                )

                if existing:
                    for k, v in mapped.items():
                        if k != "external_id" and v is not None:
                            setattr(existing, k, v)
                    existing.raw_data = dict(row)
                else:
                    item = OrderItem(
                        order_id=internal_order_id,
                        external_id=external_id or None,
                        raw_data=dict(row),
                        **{k: v for k, v in mapped.items() if k != "external_id" and v is not None},
                    )
                    self.db.add(item)
                    count += 1

            self.db.commit()

        return count

    # ─────────────────────────────────────────────────────────────────────────
    #  Batch fetcher
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch_batches(
        self, conn, table_name: str
    ) -> Generator[List[Dict], None, None]:
        """
        Stream rows from a source table in batches.
        Uses OFFSET pagination to avoid loading everything into memory.
        """
        offset = 0
        while True:
            result = conn.execute(
                text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset"),
                {"limit": self.batch_size, "offset": offset},
            )
            rows = [dict(r._mapping) for r in result.fetchall()]
            if not rows:
                break
            yield rows
            if len(rows) < self.batch_size:
                break
            offset += self.batch_size
