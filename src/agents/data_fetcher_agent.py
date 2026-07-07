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

from src.tools.llm import get_llm
from src.tools.db_tools import (
    query_customer, query_competitor_prices,
    query_kunden_historie,
)


def extract_product(nachricht: str) -> str:
    """
    Fragt DeepSeek: Welches Produkt ist im Ticket gemeint?
    Wie ein Detektiv, der aus einer Nachricht den Produktnamen rausliest.
    """
    prompt = f"""Extract the product or service name from this support ticket.
Return ONLY the product name (e.g. "Cloud-Speicher Pro", "API-Gateway", "KI-Chatbot").
If no specific product is mentioned, just return "Cloud".

Ticket: {nachricht[:500]}"""

    llm = get_llm(temperature=0.0)  # ← 0.0 = immer die gleiche Antwort bei gleicher Frage
    resp = llm.invoke(prompt)
    return resp.content.strip().rstrip(".")


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
        # Keine Tickets da → Fehler zurückgeben
        return {"error": "Keine offenen Tickets gefunden"}

    ticket = tickets[0]
    kunden_id = ticket.get("kunden_id", 1)  # ← Hier holen wir die Kunden-ID

    # ─── Stammdaten immer holen (Name, Email, Vertragstyp, Status) ───
    kunde = query_customer(kunden_id)
    collected["kunde"] = kunde

    # ─── Je nach Klassifikation: gezielt mehr Daten ───
    if classification == "preisanfrage":
        # Beispiel: "Was kostet Cloud-Speicher Pro bei der Konkurrenz?"
        produkt = extract_product(ticket.get("nachricht", ""))
        preise = query_competitor_prices(produkt)
        collected["preis_vergleich"] = preise[:5]  # max 5 Ergebnisse
        collected["produkt_name"] = produkt

    elif classification in ("beschwerde", "kuendigung"):
        # Bei Beschwerde/Kündigung: Historie checken
        # Wie viele Bestellungen? Welche Tickets gab es schon?
        historie = query_kunden_historie(kunden_id)
        collected["historie"] = historie

    else:  # sonstiges
        # Nur Basis-Daten reichen
        pass

    return collected
