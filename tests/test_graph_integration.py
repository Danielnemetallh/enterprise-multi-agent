"""
Integrationstests für den vollständigen LangGraph-Workflow.
LLM-Aufrufe und DB-Queries werden gemockt.
"""
from unittest.mock import patch, MagicMock
import pytest
from langgraph.graph import StateGraph
from src.graph.workflow import build_graph, AgentState


@pytest.fixture
def mock_ticket():
    return {
        "id": 5, "kunden_id": 1, "typ": "preisanfrage",
        "betreff": "Preis für Cloud-Speicher Pro?",
        "nachricht": "Was kostet Cloud-Speicher Pro?",
        "kunde": "Veit Klemm", "email": "veit@test.de",
    }


class TestGraphIntegration:
    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket")
    @patch("src.graph.workflow.run_data_fetcher")
    @patch("src.graph.workflow.run_executive")
    def test_preisanfrage_durchlauf(self, mock_exec, mock_fetcher, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = "preisanfrage"
        mock_fetcher.return_value = {
            "kunde": {"name": "Veit Klemm", "status": "aktiv", "vertragstyp": "Premium"},
            "preis_vergleich": [{"anbieter": "Konkurrenz", "preis": 9.99}],
        }
        mock_exec.return_value = {
            "typ": "angebot", "wert": 10, "betreff": "Angebot",
            "nachricht": "10% Rabatt für Sie.", "kritisch": False,
        }

        graph = build_graph()
        result = graph.invoke({
            "input": "",
            "ticket": None,
            "classification": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
        })

        assert result["classification"] == "preisanfrage"
        assert result["ticket"] is not None
        assert result["proposed_action"]["typ"] == "angebot"
        assert result["approval"] == "approved"
        mock_fetcher.assert_called_once_with("preisanfrage", mock_ticket)
        mock_exec.assert_called_once()

    @patch("builtins.input")
    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket")
    @patch("src.graph.workflow.run_executive")
    def test_kuendigung_durchlauf(self, mock_exec, mock_classify, mock_tickets, mock_input, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = "kuendigung"
        mock_input.return_value = "ja"
        mock_exec.return_value = {
            "typ": "angebot", "wert": 20, "betreff": "Kündigung erhalten",
            "nachricht": "20% Rabatt zum Bleiben.", "kritisch": True,
        }

        graph = build_graph()
        result = graph.invoke({
            "input": "",
            "ticket": None,
            "classification": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
        })

        assert result["classification"] == "kuendigung"
        assert result["proposed_action"]["kritisch"] is True
        assert result["approval"] == "approved"

    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket")
    @patch("src.graph.workflow.run_executive")
    def test_sonstiges_geht_direkt_zu_executive(self, mock_exec, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = "sonstiges"
        mock_exec.return_value = {
            "typ": "info", "wert": 0, "betreff": "Info",
            "nachricht": "Wir kümmern uns.", "kritisch": False,
        }

        graph = build_graph()
        result = graph.invoke({
            "input": "",
            "ticket": None,
            "classification": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
        })

        assert result["classification"] == "sonstiges"
        assert result["proposed_action"]["typ"] == "info"
