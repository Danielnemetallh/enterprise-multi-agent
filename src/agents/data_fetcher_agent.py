"""
Data-Fetcher Agent (Agent 2) — Holt Daten aus DB je nach Klassifikation
========================================================================
Analysiert das Ticket mit DeepSeek und holt gezielt die passenden Daten:
- preisanfrage  → Konkurrenz-Preise + Kundeninfos
- beschwerde    → Kunden-Historie + Bestellungen
- kuendigung    → Kunden-Historie + Vertragsdaten
- sonstiges     → Basis-Kundeninfos

Lern-Notiz: Das ist der "Wissens-Beschaffer" im Team. Während der Triage-Agent
nur fragt "Was ist das Problem?", fragt dieser Agent "Was wissen wir dazu?"
"""

import logging
from src.tools.llm import get_llm, call_llm_safe
from src.tools.db_tools import (
    query_customer, query_competitor_prices,
    query_kunden_historie,
)

logger = logging.getLogger(__name__)


def extract_product(nachricht: str) -> str:
    """
    Fragt DeepSeek: Welches Produkt ist im Ticket gemeint?
    Wie ein Detektiv, der aus einer Nachricht den Produktnamen rausliest.
    """
    prompt = f"""Extract the product or service name from this support ticket.
Return ONLY the product name (e.g. "Cloud-Speicher Pro", "API-Gateway", "KI-Chatbot").
If no specific product is mentioned, just return "Cloud".

Ticket: {nachricht[:500]}"""

    result = call_llm_safe(prompt, temperature=0.0)
    if result:
        return result.strip().rstrip(".")
    logger.warning("extract_product: LLM-Aufruf fehlgeschlagen, verwende 'Cloud'")
    return "Cloud"


def _fetch_for_ticket(ticket: dict) -> dict:
    """Holt Daten für EIN Ticket — je nach Klassifikation."""
    classification = ticket.get("classification", "sonstiges")
    kunden_id = ticket.get("kunden_id")
    collected = {}

    if not kunden_id:
        logger.warning(f"Ticket #{ticket.get('id')}: Keine Kunden-ID, überspringe")
        return {"error": "Keine Kunden-ID im Ticket"}

    # ─── Stammdaten immer holen (Name, Email, Vertragstyp, Status) ───
    try:
        collected["kunde"] = query_customer(kunden_id)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Kundendaten (ID {kunden_id}): {e}")
        collected["kunde"] = {"error": f"Kundendaten nicht verfügbar: {e}"}

    # ─── Je nach Klassifikation: gezielt mehr Daten ───
    if classification == "preisanfrage":
        try:
            produkt = extract_product(ticket.get("nachricht", ""))
            preise = query_competitor_prices(produkt)
            collected["preis_vergleich"] = preise[:5]
            collected["produkt_name"] = produkt
        except Exception as e:
            logger.error(f"Fehler beim Preisvergleich: {e}")
            collected["preis_vergleich"] = []

    elif classification in ("beschwerde", "kuendigung"):
        try:
            historie = query_kunden_historie(kunden_id)
            collected["historie"] = historie
        except Exception as e:
            logger.error(f"Fehler beim Laden der Kunden-Historie: {e}")
            collected["historie"] = {"orders": [], "tickets": []}

    else:  # sonstiges
        pass

    # Ticket-Info mitschicken, damit Executive den Bezug zum Kunden herstellen kann
    collected["ticket"] = {
        "id": ticket["id"],
        "betreff": ticket.get("betreff", ""),
        "nachricht": (ticket.get("nachricht", "") or "")[:500],
    }

    return collected


def run_data_fetcher(classification: str, tickets: list) -> dict:
    """
    Holt Daten aus DB für EIN Ticket — je nach Klassifikation.

    Nutzt die _fetch_for_ticket()-Logik (Klassifikation aus Ticket oder Parameter),
    inkl. ticket-Info für den Executive-Prompt.
    """
    if not tickets:
        return {"error": "Keine offenen Tickets gefunden"}
    ticket = dict(tickets[0])
    ticket.setdefault("classification", classification)
    return _fetch_for_ticket(ticket)
