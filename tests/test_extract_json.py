"""
Tests für extract_json() — die JSON-Extraktions-Helferfunktion.
"""
import json

import pytest

from src.tools.llm import extract_json


class TestExtractJson:
    def test_plain_json(self):
        """Nacktes JSON-Objekt ohne Markdown."""
        result = extract_json('{"typ": "angebot", "wert": 10}')
        assert result == {"typ": "angebot", "wert": 10}

    def test_markdown_json_block(self):
        """JSON in ```json ... ``` Block."""
        result = extract_json("""```json
{"typ": "info", "wert": 0}
```""")
        assert result == {"typ": "info", "wert": 0}

    def test_markdown_plain_block(self):
        """JSON in ``` ... ``` Block ohne language tag."""
        result = extract_json("""```
{"typ": "storno", "wert": 15}
```""")
        assert result == {"typ": "storno", "wert": 15}

    def test_json_with_surrounding_text(self):
        """JSON mit Text davor und danach."""
        result = extract_json(
            'Hier ist das Ergebnis: {"typ": "angebot", "wert": 5}. Ende.'
        )
        assert result == {"typ": "angebot", "wert": 5}

    def test_invalid_input_raises(self):
        """Ungültiger Input ohne JSON → Exception."""
        with pytest.raises(json.JSONDecodeError):
            extract_json("Das ist kein JSON")

    def test_empty_string_raises(self):
        """Leerer String → Exception."""
        with pytest.raises(json.JSONDecodeError):
            extract_json("")

    def test_multiple_code_blocks_first_wins(self):
        """Mehrere Code-Blöcke → erster mit gültigem JSON gewinnt."""
        result = extract_json("""
```json
{"typ": "info", "wert": 0}
```
```json
{"typ": "angebot", "wert": 99}
```""")
        assert result["typ"] == "info"

    def test_malformed_json_in_block_falls_through(self):
        """Kaputter JSON-Block → fällt auf direkte JSON-Suche zurück."""
        result = extract_json("""```json
das ist kein json
```
Aber hier ist es: {"typ": "angebot", "wert": 5}""")
        assert result["typ"] == "angebot"

    def test_deeply_nested_json(self):
        """Verschachteltes JSON mit Listen."""
        result = extract_json('{"kunde": {"name": "Test", "status": "aktiv"}, "orders": [1, 2, 3]}')
        assert result["kunde"]["name"] == "Test"
        assert len(result["orders"]) == 3
