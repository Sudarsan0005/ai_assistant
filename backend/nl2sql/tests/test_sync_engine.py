"""
tests/test_sync_engine.py
──────────────────────────
Unit tests for data sync column mapping and batch logic.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestColumnMapping:
    def test_resolves_first_matching_column(self):
        from app.core.sync.sync_engine import _resolve_value
        row = {"email_address": "test@example.com", "email": "other@example.com"}
        result = _resolve_value(row, ["email", "email_address"])
        assert result == "other@example.com"

    def test_returns_none_when_no_match(self):
        from app.core.sync.sync_engine import _resolve_value
        row = {"phone_number": "555-1234"}
        result = _resolve_value(row, ["email", "email_address"])
        assert result is None

    def test_skips_none_values(self):
        from app.core.sync.sync_engine import _resolve_value
        row = {"email": None, "email_address": "valid@example.com"}
        result = _resolve_value(row, ["email", "email_address"])
        assert result == "valid@example.com"

    def test_maps_customer_row(self):
        from app.core.sync.sync_engine import _map_row, CUSTOMER_COLUMN_MAP
        row = {
            "id": "CUST-001",
            "firstname": "Jane",
            "lname": "Doe",
            "email_address": "jane@example.com",
            "account_status": "active",
        }
        result = _map_row(row, CUSTOMER_COLUMN_MAP)
        assert result["external_id"] == "CUST-001"
        assert result["first_name"] == "Jane"
        assert result["last_name"] == "Doe"
        assert result["email"] == "jane@example.com"
        assert result["status"] == "active"

    def test_maps_order_row(self):
        from app.core.sync.sync_engine import _map_row, ORDER_COLUMN_MAP
        row = {
            "id": "ORD-101",
            "customer_id": "CUST-001",
            "grand_total": 250.00,
            "order_status": "completed",
            "order_date": "2024-06-15",
        }
        result = _map_row(row, ORDER_COLUMN_MAP)
        assert result["external_id"] == "ORD-101"
        assert result["external_customer_id"] == "CUST-001"
        assert result["total_amount"] == 250.00
        assert result["status"] == "completed"

    def test_maps_order_item_row(self):
        from app.core.sync.sync_engine import _map_row, ORDER_ITEM_COLUMN_MAP
        row = {
            "id": "ITEM-55",
            "name": "Blue T-Shirt",
            "sku_code": "SHIRT-BLU-M",
            "qty": 3,
            "price": 19.99,
        }
        result = _map_row(row, ORDER_ITEM_COLUMN_MAP)
        assert result["external_id"] == "ITEM-55"
        assert result["product_name"] == "Blue T-Shirt"
        assert result["sku"] == "SHIRT-BLU-M"
        assert result["quantity"] == 3
        assert result["unit_price"] == 19.99


class TestSourceURL:
    def test_postgresql_url(self):
        from app.core.sync.sync_engine import _build_source_url

        class FakeSource:
            db_type = "postgresql"
            username = "admin"
            host = "db.example.com"
            port = 5432
            database_name = "mydb"

        url = _build_source_url(FakeSource(), "secret")
        assert "postgresql+psycopg2" in url
        assert "admin:secret" in url
        assert "db.example.com:5432" in url
        assert "mydb" in url

    def test_mysql_url(self):
        from app.core.sync.sync_engine import _build_source_url

        class FakeSource:
            db_type = "mysql"
            username = "root"
            host = "mysql.example.com"
            port = 3306
            database_name = "shop"

        url = _build_source_url(FakeSource(), "rootpw")
        assert "mysql+pymysql" in url
