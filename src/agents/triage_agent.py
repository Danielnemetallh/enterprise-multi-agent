"""
Triage-Agent (Agent 1) — Klassifiziert eingehende Tickets via LLM
====================================================================
Mögliche Klassen: "beschwerde", "kuendigung", "preisanfrage", "sonstiges"
"""

import logging
from src.tools.llm import call_llm_safe

logger = logging.getLogger(__name__)

KLASSEN = ["beschwerde", "kuendigung", "preisanfrage", "sonstiges"]

PROMPT_TEMPLATE = """Classify the following customer support ticket into EXACTLY ONE of these categories:
- preisanfrage: customer asks about prices, discounts, offers, or price comparison
- beschwerde: customer complains about service, price, product quality, or downtime
- kuendigung: customer wants to cancel their contract or subscription
- sonstiges: anything else (account questions, documentation, feature requests, etc.)

Respond with ONLY the category name, nothing else.

Subject: {betreff}
Message: {nachricht}

Category:"""


def classify_ticket(betreff: str, nachricht: str) -> str:
    """Klassifiziert ein Ticket per LLM-Call (DeepSeek)."""
    prompt = PROMPT_TEMPLATE.format(
        betreff=betreff,
        nachricht=nachricht[:600],
    )
    result = call_llm_safe(prompt, temperature=0.0)
    if not result:
        logger.warning("LLM-Aufruf fehlgeschlagen → fallback sonstiges")
        return "sonstiges"

    result = result.strip().lower().rstrip(".")

    # Falls LLM was anderes zurückgibt
    for k in KLASSEN:
        if k in result:
            return k
    logger.warning(f"Unerwartete Antwort: '{result}' → fallback sonstiges")
    return "sonstiges"


def run_triage(tickets: list[dict]) -> list[dict]:
    """Klassifiziert mehrere Tickets."""
    for t in tickets:
        t["classification"] = classify_ticket(t["betreff"], t["nachricht"])
    return tickets


if __name__ == "__main__":
    from src.tools.db_tools import query_open_tickets

    tickets = query_open_tickets()
    result = run_triage(tickets[:5])
    for t in result:
        print(f'  [{t["classification"]}] {t["betreff"]}')
