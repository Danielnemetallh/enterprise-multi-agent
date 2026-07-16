"""
Executive Agent (Agent 3) — Creates policy-compatible solution proposals
======================================================================
LLM proposes — policy layer enforces approval rules deterministically.
"""

import json
import logging

from src.tools.llm import call_llm_safe, extract_json
from src.tools.policy import evaluate_policy

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are an executive agent for a customer support system.
Based on the ticket details below, decide on the best action.

Classification: {classification}
Priority: {priority}
Product: {product}

Customer:
- Name: {customer_name}
- Email: {customer_email}

Ticket Subject: {ticket_subject}
Ticket Description: {ticket_description}

Respond with a JSON object (ONLY JSON, no other text):
{{
    "action_type": "offer_discount|send_apology|provide_information|process_cancellation",
    "discount_percent": <number 0-30>,
    "subject": "<short subject in English>",
    "customer_message": "<response message to customer in English, max 2 sentences, no internal labels>",
    "business_reason": "<short internal reason in English>",
    "alternatives": ["<optional alternative 1>", "<optional alternative 2>"]
}}

Rules:
- offer_discount for refunds, billing goodwill, or retention offers
- send_apology for technical issues and service complaints
- provide_information for product or billing questions
- process_cancellation for cancellation requests
- discount_percent only > 0 when action_type == "offer_discount"
- customer_message must be professional English for the customer only
- do NOT mention policy, approval, LLM, or internal risk labels in customer_message

Examples:
- refund_request -> offer_discount, discount 5-15
- technical_issue -> send_apology, discount 0
- cancellation_request -> offer_discount with 10-20% retention offer or process_cancellation
- product_inquiry -> provide_information, discount 0
- billing_inquiry -> provide_information or offer_discount up to 10%
"""


def _normalize_llm_action(action: dict) -> dict:
    """Map LLM fields to the policy-ready shape."""
    action_type = action.get("action_type", "provide_information")
    discount = action.get("discount_percent", 0)
    customer_message = action.get("customer_message", "") or "We will follow up on your request shortly."

    return {
        **action,
        "action_type": action_type,
        "discount_percent": discount,
        "subject": action.get("subject", "Your support request"),
        "customer_message": customer_message,
        "business_reason": action.get("business_reason"),
        "alternatives": action.get("alternatives", []),
    }


def _fallback_action() -> dict:
    return {
        "action_type": "provide_information",
        "discount_percent": 0,
        "subject": "Your support request",
        "customer_message": "We will follow up on your request shortly.",
    }


def run_executive(classification: str, collected_data: dict) -> dict:
    """
    Create a solution proposal via LLM and apply policy rules.

    Returns action with:
    action_type, discount_percent, requires_approval, approval_reason,
    business_reason, risk_level, alternatives, customer_message
    """
    ticket = collected_data.get("ticket", {})

    prompt = PROMPT_TEMPLATE.format(
        classification=classification,
        priority=ticket.get("priority", "Unknown"),
        product=ticket.get("product", "Unknown"),
        customer_name=ticket.get("customer_name", "Unknown"),
        customer_email=ticket.get("customer_email", "unknown@example.com"),
        ticket_subject=ticket.get("subject", "No subject"),
        ticket_description=(ticket.get("description", "") or "")[:1000],
    )

    result = call_llm_safe(prompt, temperature=0.0)
    if not result:
        logger.warning("Executive: LLM call failed, using fallback action")
        return evaluate_policy(_fallback_action(), classification, ticket)

    try:
        action = extract_json(result)
        action = _normalize_llm_action(action)
        action = evaluate_policy(action, classification, ticket)

        logger.info(
            "Executive: %s | %s | Discount: %s%% | Approval: %s",
            action["action_type"],
            action.get("subject", "")[:50],
            action["discount_percent"],
            action["requires_approval"],
        )
        return action

    except (json.JSONDecodeError, IndexError) as exc:
        logger.warning("Executive: could not parse response: %s", exc)
        return evaluate_policy(_fallback_action(), classification, ticket)
