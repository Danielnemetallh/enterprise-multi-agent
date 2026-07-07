"""
Tests für den Triage-Agent — klassifiziert Tickets.
LLM-Aufrufe werden gemockt, damit die Tests schnell und API-unabhängig sind.
"""
from unittest.mock import patch
import pytest
from src.agents.triage_agent import classify_ticket, run_triage


class TestClassifyTicket:
    """classify_ticket() mit gemocktem DeepSeek."""

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_preisanfrage(self, mock_llm):
        mock_llm.return_value = "preisanfrage"
        result = classify_ticket("Was kostet XYZ?", "Ich möchte einen Preis.")
        assert result == "preisanfrage"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_beschwerde(self, mock_llm):
        mock_llm.return_value = "beschwerde"
        result = classify_ticket("Schlechter Service", "Ich bin unzufrieden.")
        assert result == "beschwerde"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_kuendigung(self, mock_llm):
        mock_llm.return_value = "kuendigung"
        result = classify_ticket("Kündigung", "Hiermit kündige ich.")
        assert result == "kuendigung"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_sonstiges(self, mock_llm):
        mock_llm.return_value = "sonstiges"
        result = classify_ticket("Frage zur Rechnung", "Wo ist meine Rechnung?")
        assert result == "sonstiges"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_fallback_bei_unerwarteter_antwort(self, mock_llm):
        """Wenn das LLM etwas Unerwartetes zurückgibt → fallback 'sonstiges'."""
        mock_llm.return_value = "irgendein-quatsch"
        result = classify_ticket("Test", "Test")
        assert result == "sonstiges"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_gross_kleinschreibung_normalisiert(self, mock_llm):
        mock_llm.return_value = "PREISANFRAGE"
        result = classify_ticket("Preis?", "Was kostet das?")
        assert result == "preisanfrage"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_punkt_am_ende_entfernt(self, mock_llm):
        mock_llm.return_value = "beschwerde."
        result = classify_ticket("Problem", "Hilfe!")
        assert result == "beschwerde"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_fallback_bei_llm_fehler(self, mock_llm):
        """Wenn call_llm_safe None zurückgibt (API-Fehler) → fallback 'sonstiges'."""
        mock_llm.return_value = None
        result = classify_ticket("Test", "Test")
        assert result == "sonstiges"


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
