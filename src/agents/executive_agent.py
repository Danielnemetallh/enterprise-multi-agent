"""
Executive Agent (Agent 3) — Erstellt Lösungsvorschläge per DeepSeek
====================================================================
Nimmt die gesammelten Daten und entscheidet:
- Welcher Rabatt ist angemessen?
- Soll die Aktion automatisch ausgeführt werden oder braucht es Freigabe?
- Formuliert eine Antwort an den Kunden

Lern-Notiz: Das ist der "Manager" im Team. Er kriegt alle Infos (Was ist das Problem?
+ Was wissen wir dazu?) und sagt dann: "So sollten wir reagieren."
"""

import json
import logging
from src.tools.llm import call_llm_safe, extract_json

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """You are an executive agent for a customer support system.
Based on the following data, decide on the best action.

Classification: {classification}

Customer Info:
- Name: {kunde_name}
- Status: {kunde_status}
- Vertrag: {kunde_vertrag}

Additional Data:
{collected_data}

Respond with a JSON object (ONLY JSON, no other text):
{{
    "typ": "angebot|entschuldigung|info|storno",
    "wert": <number 0-30>,
    "betreff": "<short subject in German>",
    "nachricht": "<response message to customer in German>",
    "kritisch": true/false
}}

Rules:
- "typ": "angebot" für Rabatt-Angebote, "entschuldigung" für Beschwerden,
         "info" für allgemeine Infos, "storno" für Kündigungen
- "wert": Rabatt in Prozent (0 = kein Rabatt). Nur >0 wenn "typ" == "angebot"
- "kritisch": true wenn wert > 15, oder bei Kündigungen/Kulanz
- "nachricht": max 2 Sätze, professionell und freundlich

Examples:
- Kunde fragt nach Preis → angebot, wert 10-20, kritisch wenn >15
- Kunde beschwert sich → entschuldigung + kleiner Rabatt (5-10%), kritisch false
- Kunde kündigt → angebot mit 15-25% Rabatt, kritisch true
- Sonstiges → info, wert 0, kritisch false
"""


def run_executive(classification: str, collected_data: dict) -> dict:
    """
    Hauptfunktion: Erstellt einen Lösungsvorschlag per DeepSeek.

    Das ist der wichtigste Agent im System – er entscheidet WAS passieren soll.
    Der Data-Fetcher liefert nur die Informationen, aber der Executive
    bestimmt die Aktion.

    Parameter:
    - classification: Die Ticket-Klasse vom Triage-Agent
    - collected_data: Alle Daten vom Data-Fetcher

    Rückgabe:
    - dict mit: typ, wert, betreff, nachricht, kritisch
    """

    # Kunde aus den gesammelten Daten holen
    kunde = collected_data.get("kunde", {})

    # Daten für den Prompt aufbereiten (ohne riesige Dicts)
    collected_summary = {}
    for key, value in collected_data.items():
        if key == "kunde":
            continue  # Den haben wir schon extra
        if isinstance(value, list):
            collected_summary[key] = f"[{len(value)} Einträge]"
            if value:
                collected_summary[f"{key}_beispiel"] = value[0]
        elif isinstance(value, dict):
            collected_summary[key] = value

    prompt = PROMPT_TEMPLATE.format(
        classification=classification,
        kunde_name=kunde.get("name", "Unbekannt"),
        kunde_status=kunde.get("status", "Unbekannt"),
        kunde_vertrag=kunde.get("vertragstyp", "Unbekannt"),
        collected_data=json.dumps(collected_summary, indent=2, ensure_ascii=False),
    )

    result = call_llm_safe(prompt, temperature=0.0)
    if not result:
        logger.warning("Executive: LLM-Aufruf fehlgeschlagen, verwende Fallback")
        return {
            "typ": "info",
            "wert": 0,
            "betreff": "Ihre Anfrage",
            "nachricht": "Wir werden uns um Ihr Anliegen kümmern.",
            "kritisch": False,
        }

    # JSON aus der Antwort extrahieren
    try:
        action = extract_json(result)

        # Sicherstellen, dass alle Felder da sind
        action.setdefault("typ", "info")
        action.setdefault("wert", 0)
        action.setdefault("betreff", "Ihre Anfrage")
        action.setdefault("nachricht", "Wir werden uns um Ihr Anliegen kümmern.")
        action.setdefault("kritisch", action.get("wert", 0) > 15)

        logger.info(f"Executive: {action['typ']} | {action.get('betreff', '')[:50]} | Wert: {action['wert']}% | Kritisch: {action['kritisch']}")
        return action

    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Executive: Konnte Antwort nicht parsen: {e}")
        logger.debug(f"Antwort war: {result[:200]}")
        return {
            "typ": "info",
            "wert": 0,
            "betreff": "Ihre Anfrage",
            "nachricht": "Wir werden uns um Ihr Anliegen kümmern.",
            "kritisch": False,
        }
