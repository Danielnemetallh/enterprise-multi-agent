"""
Tests für den Triage-Agent — klassifiziert Tickets.
LLM-Aufrufe werden gemockt, damit die Tests schnell und API-unabhängig sind.
"""
from unittest.mock import patch, MagicMock
import pytest
from src.agents.triage_agent import classify_ticket, run_triage


class MockLLMResponse:
    """Simuliert eine LangChain-LLM-Antwort."""
    def __init__(self, content: str):
        self.content = content


class TestClassifyTicket:
    """classify_ticket() mit gemocktem DeepSeek."""

    @patch("src.agents.triage_agent.get_llm")
    def test_preisanfrage(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("preisanfrage")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Was kostet XYZ?", "Ich möchte einen Preis.")
        assert result == "preisanfrage"

    @patch("src.agents.triage_agent.get_llm")
    def test_beschwerde(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("beschwerde")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Schlechter Service", "Ich bin unzufrieden.")
        assert result == "beschwerde"

    @patch("src.agents.triage_agent.get_llm")
    def test_kuendigung(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("kuendigung")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Kündigung", "Hiermit kündige ich.")
        assert result == "kuendigung"

    @patch("src.agents.triage_agent.get_llm")
    def test_sonstiges(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("sonstiges")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Frage zur Rechnung", "Wo ist meine Rechnung?")
        assert result == "sonstiges"

    @patch("src.agents.triage_agent.get_llm")
    def test_fallback_bei_unerwarteter_antwort(self, mock_get_llm):
        """Wenn das LLM etwas Unerwartetes zurückgibt → fallback 'sonstiges'."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("irgendein-quatsch")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Test", "Test")
        assert result == "sonstiges"

    @patch("src.agents.triage_agent.get_llm")
    def test_gross_kleinschreibung_normalisiert(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("PREISANFRAGE")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Preis?", "Was kostet das?")
        assert result == "preisanfrage"

    @patch("src.agents.triage_agent.get_llm")
    def test_punkt_am_ende_entfernt(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("beschwerde.")
        mock_get_llm.return_value = mock_llm

        result = classify_ticket("Problem", "Hilfe!")
        assert result == "beschwerde"


class TestRunTriage:
    """run_triage() verarbeitet mehrere Tickets."""

    @patch("src.agents.triage_agent.classify_ticket")
    def test_klassifiziert_alle_tickets(self, mock_classify):
        mock_classify.return_value = "sonstiges"
        tickets = [
            {"betreff": "A", "nachricht": "Nachricht A"},
            {"betreff": "B", "nachricht": "Nachricht B"},
            {"betreff": "C", "nachricht": "Nachricht C"},
        ]
        result = run_triage(tickets)
        assert len(result) == 3
        assert all(t["classification"] == "sonstiges" for t in result)
