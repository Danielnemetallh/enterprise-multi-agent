"""
Tests für den Executive-Agent — erstellt Lösungsvorschläge.
LLM-Aufrufe werden gemockt.
"""
from unittest.mock import patch, MagicMock
import pytest
from src.agents.executive_agent import run_executive


class TestRunExecutive:
    """run_executive() mit gemocktem DeepSeek."""

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_preisanfrage_erzeugt_angebot(self, mock_llm):
        mock_llm.return_value = """{
            "typ": "angebot",
            "wert": 15,
            "betreff": "Ihr Preisvorschlag",
            "nachricht": "Wir bieten Ihnen 15% Rabatt.",
            "kritisch": false
        }"""
        collected = {
            "kunde": {"name": "Max Test", "status": "aktiv", "vertragstyp": "Premium"},
            "preis_vergleich": [{"anbieter": "Konkurrenz", "preis": 9.99}],
        }
        result = run_executive("preisanfrage", collected)
        assert result["typ"] == "angebot"
        assert result["wert"] == 15
        assert result["kritisch"] is False

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_kuendigung_ist_kritisch(self, mock_llm):
        mock_llm.return_value = """{
            "typ": "angebot",
            "wert": 20,
            "betreff": "Kündigung erhalten",
            "nachricht": "Wir möchten Sie mit 20% Rabatt halten.",
            "kritisch": true
        }"""
        collected = {
            "kunde": {"name": "Hans K.", "status": "aktiv", "vertragstyp": "Business"},
            "historie": {"orders": [], "tickets": []},
        }
        result = run_executive("kuendigung", collected)
        assert result["typ"] == "angebot"
        assert result["kritisch"] is True

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_fallback_bei_parsing_fehler(self, mock_llm):
        """Wenn das LLM kaputtes JSON liefert → Fallback-Werte."""
        mock_llm.return_value = "Das ist kein JSON"
        collected = {"kunde": {"name": "Test"}}
        result = run_executive("sonstiges", collected)
        assert result["typ"] == "info"
        assert result["wert"] == 0
        assert result["kritisch"] is False

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_markdown_code_block(self, mock_llm):
        """LLM antwortet mit ```json Block."""
        mock_llm.return_value = """```json
{
    "typ": "info",
    "wert": 0,
    "betreff": "Ihre Anfrage",
    "nachricht": "Wir kümmern uns darum.",
    "kritisch": false
}
```"""
        result = run_executive("sonstiges", {"kunde": {"name": "Test"}})
        assert result["typ"] == "info"

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_defaults_fehlen_werden_gesetzt(self, mock_llm):
        """Wenn das LLM Felder auslässt → Defaults setzen."""
        mock_llm.return_value = '{"typ": "angebot"}'
        result = run_executive("preisanfrage", {"kunde": {"name": "Test", "status": "aktiv", "vertragstyp": "Basic"}})
        assert result["wert"] == 0       # Default
        assert result["betreff"]         # Default-Betreff
        assert result["nachricht"]       # Default-Nachricht
        assert result["kritisch"] is False  # Default (0 > 15 = False)

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_fallback_bei_llm_fehler(self, mock_llm):
        """Wenn call_llm_safe None zurückgibt → Fallback-Aktion."""
        mock_llm.return_value = None
        collected = {"kunde": {"name": "Test"}}
        result = run_executive("preisanfrage", collected)
        assert result["typ"] == "info"
        assert result["wert"] == 0
