"""
Tests für den Data-Fetcher Agent — sammelt Daten je nach Klassifikation.
LLM-Aufrufe (extract_product) werden gemockt, DB-Zugriffe sind echt.
"""
from unittest.mock import patch
import pytest
from src.agents.data_fetcher_agent import run_data_fetcher


@pytest.fixture
def mock_tickets():
    return [
        {"id": 1, "kunden_id": 1, "typ": "preisanfrage",
         "betreff": "Preis für Cloud-Speicher Pro?",
         "nachricht": "Was kostet Cloud-Speicher Pro?",
         "kunde": "Veit Klemm", "email": "veit@test.de"},
    ]


class TestRunDataFetcher:
    @patch("src.agents.data_fetcher_agent.call_llm_safe")
    def test_preisanfrage_holt_preise_und_kunde(self, mock_llm, mock_tickets):
        mock_llm.return_value = "Cloud-Speicher Pro"

        result = run_data_fetcher("preisanfrage", mock_tickets)
        assert "kunde" in result
        assert "preis_vergleich" in result
        assert "produkt_name" in result
        assert result["produkt_name"] == "Cloud-Speicher Pro"
        assert len(result["preis_vergleich"]) > 0

    def test_beschwerde_holt_historie(self, mock_tickets):
        result = run_data_fetcher("beschwerde", mock_tickets)
        assert "kunde" in result
        assert "historie" in result
        assert "orders" in result["historie"]
        assert "tickets" in result["historie"]

    def test_kuendigung_holt_historie(self, mock_tickets):
        result = run_data_fetcher("kuendigung", mock_tickets)
        assert "kunde" in result
        assert "historie" in result

    def test_sonstiges_nur_kunde(self, mock_tickets):
        result = run_data_fetcher("sonstiges", mock_tickets)
        assert "kunde" in result
        assert "historie" not in result
        assert "preis_vergleich" not in result

    def test_keine_tickets(self):
        result = run_data_fetcher("preisanfrage", [])
        assert "error" in result
