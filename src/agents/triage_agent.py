"""
Triage Agent (Agent 1) — Classifies incoming support tickets
=============================================================
Uses normalized metadata from imported tickets first.
Calls the LLM only for missing, unknown, or high-risk categories.
"""

import logging

from src.tools.llm import call_llm_safe
from src.tools.ticket_schema import INTERNAL_CATEGORIES, should_use_llm_for_triage

logger = logging.getLogger(__name__)

CATEGORIES = list(INTERNAL_CATEGORIES)

PROMPT_TEMPLATE = """Classify the following customer support ticket into EXACTLY ONE of these categories:
- technical_issue: customer reports a product defect, outage, or technical problem
- refund_request: customer asks for a refund or charge reversal
- cancellation_request: customer wants to cancel their contract or subscription
- product_inquiry: customer asks about product features, pricing, or availability
- billing_inquiry: customer asks about invoices, charges, or payment issues

Respond with ONLY the category name, nothing else.

Subject: {subject}
Message: {description}

Category:"""


def classify_ticket(subject: str, description: str) -> str:
    """Classify a ticket via LLM call."""
    prompt = PROMPT_TEMPLATE.format(
        subject=subject,
        description=description[:600],
    )
    result = call_llm_safe(prompt, temperature=0.0)
    if not result:
        logger.warning("LLM call failed -> fallback product_inquiry")
        return "product_inquiry"

    result = result.strip().lower().rstrip(".")

    for category in CATEGORIES:
        if category in result:
            return category
    logger.warning("Unexpected LLM response '%s' -> fallback product_inquiry", result)
    return "product_inquiry"


def classify_ticket_smart(ticket: dict) -> tuple[str, str]:
    """
    Metadata-first triage.

    Returns:
        (classification, source) where source is one of:
        metadata | llm | llm_validated
    """
    subject = ticket.get("subject", "")
    description = ticket.get("description", "")
    existing_category = ticket.get("category", "")

    if not should_use_llm_for_triage(ticket):
        logger.info("Triage metadata: [%s] #%s", existing_category, ticket.get("id", "?"))
        return existing_category, "metadata"

    llm_result = classify_ticket(subject, description)
    if existing_category and existing_category in CATEGORIES and existing_category == llm_result:
        source = "llm_validated"
    else:
        source = "llm"

    logger.info(
        "Triage %s: [%s] #%s (metadata was '%s')",
        source,
        llm_result,
        ticket.get("id", "?"),
        existing_category or "-",
    )
    return llm_result, source


def run_triage(tickets: list[dict]) -> list[dict]:
    """Classify multiple tickets."""
    for ticket in tickets:
        classification, source = classify_ticket_smart(ticket)
        ticket["classification"] = classification
        ticket["triage_source"] = source
    return tickets


if __name__ == "__main__":
    from src.tools.db_tools import query_open_tickets

    tickets = query_open_tickets()
    result = run_triage(tickets[:5])
    for ticket in result:
        print(f'  [{ticket["classification"]}] ({ticket.get("triage_source", "?")}) {ticket["subject"]}')
