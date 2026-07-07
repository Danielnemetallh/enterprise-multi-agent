"""
Tests für DB-Tools — Query-Funktionen und Context-Manager.
Nutzt die echte Mock-DB (data/mock_customers.db).
"""
import pytest
from src.tools.db_tools import (
    db_connection,
    query_customer,
    query_open_tickets,
    query_kunden_historie,
    query_competitor_prices,
)


class TestDBConnection:
    """db_connection context manager."""

    def test_context_manager_schliesst_verbindung(self):
        """Nach dem with-Block ist die Verbindung zu."""
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
        # conn sollte geschlossen sein
        with pytest.raises(Exception):
            cur.execute("SELECT 1")


class TestQueryCustomer:
    def test_kunde_gefunden(self):
        kunde = query_customer(1)
        assert kunde["id"] == 1
        assert kunde["name"]
        assert kunde["email"]
        assert "phone" in kunde      # neues Feld!

    def test_kunde_nicht_gefunden(self):
        kunde = query_customer(9999)
        assert "error" in kunde

    def test_alle_felder_vorhanden(self):
        kunde = query_customer(1)
        expected_fields = {"id", "name", "email", "phone", "status",
                          "vertragstyp", "beitritt", "kundenseit"}
        assert expected_fields.issubset(kunde.keys()), f"Fehlende Felder: {expected_fields - kunde.keys()}"


class TestQueryOpenTickets:
    def test_default_limit(self):
        tickets = query_open_tickets()
        assert len(tickets) > 0
        # Filtert nur nicht-erledigte (WHERE status != 'erledigt' in SQL)
        assert len(tickets) <= 30  # Default-Limit

    def test_custom_limit(self):
        tickets = query_open_tickets(limit=3)
        assert len(tickets) <= 3

    def test_ticket_struktur(self):
        tickets = query_open_tickets(limit=1)
        assert len(tickets) == 1
        t = tickets[0]
        assert "id" in t
        assert "kunden_id" in t
        assert "betreff" in t
        assert "nachricht" in t
        assert "kunde" in t   # Kundennamen aus JOIN
        assert "email" in t


class TestQueryKundenHistorie:
    def test_historie_hat_orders_und_tickets(self):
        hist = query_kunden_historie(1)
        assert "orders" in hist
        assert "tickets" in hist

    def test_kunde_ohne_bestellungen(self):
        # Kunde 9999 existiert nicht → leere Historie
        hist = query_kunden_historie(9999)
        assert hist["orders"] == []
        assert hist["tickets"] == []


class TestQueryCompetitorPrices:
    def test_produkt_gefunden(self):
        preise = query_competitor_prices("Cloud")
        assert len(preise) > 0
        assert "anbieter" in preise[0]
        assert "preis" in preise[0]

    def test_unbekanntes_produkt(self):
        preise = query_competitor_prices("NichtexistierendesProduktXYZ")
        assert preise == []
