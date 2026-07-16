"""Tests for CSV ticket import."""
import json
import os
import sqlite3

import pandas as pd
import pytest

from src.tools import db_tools
from src.tools.import_tickets import import_tickets_from_csv, normalize_ticket_row


FIXTURE_CSV = os.path.join(os.path.dirname(__file__), "fixtures", "kaggle_sample.csv")
MAPPING_JSON = os.path.join(
    os.path.dirname(__file__), "..", "data", "mappings", "kaggle_support.json"
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_tools, "DB_PATH", str(db_path))
    db_tools.create_database(force=True)
    yield str(db_path)


class TestImportTickets:
    def test_kaggle_csv_imports_successfully(self, temp_db):
        result = import_tickets_from_csv(FIXTURE_CSV, MAPPING_JSON, force=True)
        assert result["imported"] == 5
        assert result["source_dataset"] == "kaggle_customer_support"

        with sqlite3.connect(temp_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM support_tickets WHERE source_dataset = ?",
                ("kaggle_customer_support",),
            ).fetchone()[0]
        assert count == 5

    def test_placeholder_replaced_on_import(self, temp_db):
        import_tickets_from_csv(FIXTURE_CSV, MAPPING_JSON, force=True, limit=1)
        with sqlite3.connect(temp_db) as conn:
            row = conn.execute(
                "SELECT subject, description, product FROM support_tickets "
                "WHERE source_dataset = 'kaggle_customer_support' LIMIT 1"
            ).fetchone()
        assert "{product_purchased}" not in row[0]
        assert "{product_purchased}" not in row[1]
        assert row[2] == "Cloud-Speicher Pro"

    def test_category_and_status_normalize(self, temp_db):
        import_tickets_from_csv(FIXTURE_CSV, MAPPING_JSON, force=True)
        with sqlite3.connect(temp_db) as conn:
            rows = conn.execute(
                "SELECT category, status, ticket_id FROM support_tickets "
                "WHERE source_dataset = 'kaggle_customer_support' ORDER BY ticket_id"
            ).fetchall()

        assert rows[0][0] == "product_inquiry"
        assert rows[1][0] == "cancellation_request"
        assert rows[2][0] == "technical_issue"
        assert rows[2][1] == "closed"
        assert rows[4][1] == "pending"

    def test_missing_required_headers_raise_clear_error(self, temp_db, tmp_path):
        csv_path = tmp_path / "invalid.csv"
        csv_path.write_text("Ticket ID,Customer Name\n1,Anna\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required headers"):
            import_tickets_from_csv(str(csv_path), MAPPING_JSON, force=True)

    def test_normalize_ticket_row_mapping(self, temp_db):
        with open(MAPPING_JSON, encoding="utf-8") as handle:
            mapping = json.load(handle)
        df = pd.read_csv(FIXTURE_CSV)
        row = df.iloc[1]
        ticket = normalize_ticket_row(row, mapping)
        assert ticket["category"] == "cancellation_request"
        assert ticket["priority"] == "High"
        assert ticket["source_dataset"] == "kaggle_customer_support"
        assert ticket["customer_name"] == "Ben Mueller"
