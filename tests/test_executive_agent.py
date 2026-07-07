"""
Tests für den Executive-Agent — erstellt Lösungsvorschläge.
LLM-Aufrufe werden gemockt.
"""
from unittest.mock import patch, MagicMock
import pytest
from src.agents.executive_agent import run_executive


class MockLLMResponse:
    def __init__(self, content: str):
        self.content = content


class TestRunExecutive:
    """run_executive() mit gemocktem DeepSeek."""

    @patch("src.agents.executive_agent.get_llm")
    def test_preisanfrage_erzeugt_angebot(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("""{
            "typ": "angebot",
            "wert": 15,
            "betreff": "Ihr Preisvorschlag",
            "nachricht": "Wir bieten Ihnen 15% Rabatt.",
            "kritisch": false
        }""")
        mock_get_llm.return_value = mock_llm

        collected = {
            "kunde": {"name": "Max Test", "status": "aktiv", "vertragstyp": "Premium"},
            "preis_vergleich": [{"anbieter": "Konkurrenz", "preis": 9.99}],
        }
        result = run_executive("preisanfrage", collected)
        assert result["typ"] == "angebot"
        assert result["wert"] == 15
        assert result["kritisch"] is False

    @patch("src.agents.executive_agent.get_llm")
    def test_kuendigung_ist_kritisch(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("""{
            "typ": "angebot",
            "wert": 20,
            "betreff": "Kündigung erhalten",
            "nachricht": "Wir möchten Sie mit 20% Rabatt halten.",
            "kritisch": true
        }""")
        mock_get_llm.return_value = mock_llm

        collected = {
            "kunde": {"name": "Hans K.", "status": "aktiv", "vertragstyp": "Business"},
            "historie": {"orders": [], "tickets": []},
        }
        result = run_executive("kuendigung", collected)
        assert result["typ"] == "angebot"
        assert result["kritisch"] is True

    @patch("src.agents.executive_agent.get_llm")
    def test_fallback_bei_parsing_fehler(self, mock_get_llm):
        """Wenn das LLM kaputtes JSON liefert → Fallback-Werte."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("""Das ist kein JSON""")
        mock_get_llm.return_value = mock_llm

        collected = {"kunde": {"name": "Test"}}
        result = run_executive("sonstiges", collected)
        assert result["typ"] == "info"
        assert result["wert"] == 0
        assert result["kritisch"] is False

    @patch("src.agents.executive_agent.get_llm")
    def test_markdown_code_block(self, mock_get_llm):
        """LLM antwortet mit ```json Block."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse("""```json
{
    "typ": "info",
    "wert": 0,
    "betreff": "Ihre Anfrage",
    "nachricht": "Wir kümmern uns darum.",
    "kritisch": false
}
```""")
        mock_get_llm.return_value = mock_llm

        result = run_executive("sonstiges", {"kunde": {"name": "Test"}})
        assert result["typ"] == "info"

    @patch("src.agents.executive_agent.get_llm")
    def test_defaults_fehlen_werden_gesetzt(self, mock_get_llm):
        """Wenn das LLM Felder auslässt → Defaults setzen."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MockLLMResponse('{"typ": "angebot"}')
        mock_get_llm.return_value = mock_llm

        result = run_executive("preisanfrage", {"kunde": {"name": "Test", "status": "aktiv", "vertragstyp": "Basic"}})
        assert result["wert"] == 0       # Default
        assert result["betreff"]         # Default-Betreff
        assert result["nachricht"]       # Default-Nachricht
        assert result["kritisch"] is False  # Default (0 > 15 = False)
