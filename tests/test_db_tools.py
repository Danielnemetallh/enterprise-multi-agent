"""Tests for ticket store query functions."""
import pytest

from src.tools.db_tools import (
    bulk_insert_tickets,
    create_database,
    db_connection,
    mark_ticket_processed,
    query_open_tickets,
    query_ticket_by_id,
)


@pytest.fixture
def populated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "support_tickets.db"
    monkeypatch.setattr("src.tools.db_tools.DB_PATH", str(db_path))
    create_database(force=True)
    bulk_insert_tickets([
        {
            "ticket_id": "T-1",
            "customer_name": "Anna",
            "customer_email": "anna@example.com",
            "category": "product_inquiry",
            "category_raw": "Product inquiry",
            "subject": "Pricing question",
            "description": "What does it cost?",
            "status": "open",
            "priority": "Low",
            "product": "Cloud Storage Pro",
            "channel": "Email",
            "resolution": None,
            "satisfaction_rating": None,
            "source_dataset": "test_dataset",
            "processed_at": None,
            "created_at": "2026-01-02T10:00:00",
        },
        {
            "ticket_id": "T-2",
            "customer_name": "Ben",
            "customer_email": "ben@example.com",
            "category": "cancellation_request",
            "category_raw": "Cancellation request",
            "subject": "Cancel contract",
            "description": "Please cancel my plan.",
            "status": "open",
            "priority": "High",
            "product": "API Gateway",
            "channel": "Phone",
            "resolution": None,
            "satisfaction_rating": None,
            "source_dataset": "test_dataset",
            "processed_at": None,
            "created_at": "2026-01-02T11:00:00",
        },
        {
            "ticket_id": "T-3",
            "customer_name": "Clara",
            "customer_email": "clara@example.com",
            "category": "technical_issue",
            "category_raw": "Technical issue",
            "subject": "Outage",
            "description": "Service was down.",
            "status": "closed",
            "priority": "Medium",
            "product": "VPN",
            "channel": "Chat",
            "resolution": "Resolved",
            "satisfaction_rating": 4.0,
            "source_dataset": "test_dataset",
            "processed_at": None,
            "created_at": "2026-01-02T12:00:00",
        },
    ])
    return str(db_path)


class TestDBConnection:
    def test_context_manager_closes_connection(self, populated_db):
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1


class TestQueryOpenTickets:
    def test_returns_open_unprocessed_tickets(self, populated_db):
        tickets = query_open_tickets()
        assert len(tickets) == 2
        assert tickets[0]["priority"] == "High"

    def test_custom_limit(self, populated_db):
        tickets = query_open_tickets(limit=1)
        assert len(tickets) == 1

    def test_ticket_structure(self, populated_db):
        ticket = query_open_tickets(limit=1)[0]
        expected = {
            "id", "ticket_id", "customer_name", "customer_email", "category",
            "category_raw", "created_at",
            "subject", "description", "status", "priority", "product", "channel",
            "resolution", "satisfaction_rating", "source_dataset", "processed_at",
        }
        assert expected.issubset(ticket.keys())

    def test_processed_tickets_excluded(self, populated_db):
        tickets = query_open_tickets()
        mark_ticket_processed(tickets[0]["id"])
        remaining = query_open_tickets()
        assert len(remaining) == 1

    def test_same_priority_is_ordered_oldest_first(self, populated_db):
        bulk_insert_tickets([
            {
                "ticket_id": "T-4",
                "customer_name": "Dora",
                "customer_email": "dora@example.com",
                "category": "billing_inquiry",
                "category_raw": "Billing inquiry",
                "subject": "Older",
                "description": "Older medium-priority ticket",
                "status": "open",
                "priority": "Medium",
                "source_dataset": "test_dataset",
                "created_at": "2025-12-01T08:00:00",
            },
            {
                "ticket_id": "T-5",
                "customer_name": "Emil",
                "customer_email": "emil@example.com",
                "category": "billing_inquiry",
                "category_raw": "Billing inquiry",
                "subject": "Newer",
                "description": "Newer medium-priority ticket",
                "status": "open",
                "priority": "Medium",
                "source_dataset": "test_dataset",
                "created_at": "2026-01-01T08:00:00",
            },
        ])
        medium_tickets = [ticket for ticket in query_open_tickets() if ticket["priority"] == "Medium"]
        assert [ticket["ticket_id"] for ticket in medium_tickets] == ["T-4", "T-5"]


class TestQueryTicketById:
    def test_ticket_found(self, populated_db):
        ticket = query_ticket_by_id(1)
        assert ticket is not None
        assert ticket["ticket_id"] == "T-1"

    def test_ticket_not_found(self, populated_db):
        assert query_ticket_by_id(9999) is None
