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


def run_data_fetcher(classification: str, tickets: list) -> dict:
    """
    Hauptfunktion: Sammelt Daten basierend auf der Klassifikation.

    So funktioniert's:
    1. Nimmt das erste offene Ticket
    2. Holt die Kunden-ID aus dem Ticket
    3. Ruft je nach Klassifikation die passenden DB-Funktionen auf
    4. Gibt alles gesammelt zurück

    Parameter:
    - classification: "beschwerde" | "kuendigung" | "preisanfrage" | "sonstiges"
    - tickets: Liste offener Tickets (vom Triage-Agent vorbereitet)

    Rückgabe:
    - dict mit allen gesammelten Daten (Kunde, Preise, Historie, ...)
    """
    collected = {}

    if not tickets:
        return {"error": "Keine offenen Tickets gefunden"}

    ticket = tickets[0]
    kunden_id = ticket.get("kunden_id")
    if not kunden_id:
        logger.warning("Keine Kunden-ID im Ticket, überspringe Data-Fetching")
        return {"error": "Keine Kunden-ID im Ticket"}

    # ─── Stammdaten immer holen (Name, Email, Vertragstyp, Status) ───
    try:
        kunde = query_customer(kunden_id)
        collected["kunde"] = kunde
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

    return collected
