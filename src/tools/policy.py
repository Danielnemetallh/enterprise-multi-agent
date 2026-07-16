"""
Deterministic business policy layer for executive actions.
LLM proposes — code enforces approval rules.
"""

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

ACTION_TYPES = (
    "offer_discount",
    "send_apology",
    "provide_information",
    "process_cancellation",
)

SUPPORT_POLICIES = {
    "technical_issue": {
        "allowed_actions": ("send_apology", "provide_information"),
        "default_action": "send_apology",
        "guidance": "Acknowledge the issue and provide troubleshooting steps.",
    },
    "refund_request": {
        "allowed_actions": ("offer_discount", "provide_information"),
        "default_action": "offer_discount",
        "guidance": "Offer a partial discount before escalating to a full refund.",
    },
    "cancellation_request": {
        "allowed_actions": ("offer_discount", "process_cancellation"),
        "default_action": "process_cancellation",
        "guidance": "Attempt retention with a discount before processing cancellation.",
    },
    "product_inquiry": {
        "allowed_actions": ("provide_information", "offer_discount"),
        "default_action": "provide_information",
        "guidance": "Answer product questions clearly and offer a discount when relevant.",
    },
    "billing_inquiry": {
        "allowed_actions": ("provide_information", "offer_discount"),
        "default_action": "provide_information",
        "guidance": "Clarify billing details and offer a goodwill discount when appropriate.",
    },
}


def _risk_level(action_type: str, discount: float, requires_approval: bool) -> str:
    if action_type == "process_cancellation" or discount > 20:
        return RISK_HIGH
    if requires_approval or discount > 10:
        return RISK_MEDIUM
    return RISK_LOW


def _priority_requires_approval(priority: str | None) -> bool:
    return str(priority or "").lower() in {"critical", "high"}


def evaluate_policy(
    action: dict,
    category: str,
    ticket: dict | None = None,
) -> dict:
    """
    Evaluate an executive proposal against fixed support policies.

    Returns the action enriched with policy fields and approval outcome.
    """
    discount = float(action.get("discount_percent", 0) or 0)
    action_type = action.get("action_type", "provide_information")
    customer_message = action.get("customer_message", "") or "We will follow up on your request shortly."
    priority = (ticket or {}).get("priority")
    policy = SUPPORT_POLICIES.get(category, SUPPORT_POLICIES["product_inquiry"])

    approval_reasons: list[str] = []
    business_reasons: list[str] = []
    rejected = False
    rejection_reason = None

    if action_type not in policy["allowed_actions"]:
        rejected = True
        rejection_reason = (
            f"Action '{action_type}' is not allowed for category '{category}'"
        )

    if action_type == "process_cancellation":
        approval_reasons.append("Cancellation requests require human approval")

    if action_type == "offer_discount" and discount > 15:
        approval_reasons.append(f"Discount {discount:.0f}% exceeds the 15% policy limit")

    if (
        action_type == "offer_discount"
        and discount <= 15
        and _priority_requires_approval(priority)
    ):
        approval_reasons.append(
            f"Discount of {discount:.0f}% requires approval for {priority} priority tickets"
        )

    if category == "cancellation_request":
        business_reasons.append("Retention offer recommended before cancellation")

    requires_approval = bool(approval_reasons) and not rejected

    risk = _risk_level(action_type, discount, requires_approval)
    alternatives = action.get("alternatives")
    if not alternatives and category == "cancellation_request":
        alternatives = ["Account manager callback", "Contract pause instead of cancellation"]

    return {
        **action,
        "action_type": action_type,
        "discount_percent": discount,
        "subject": action.get("subject", "Your support request"),
        "customer_message": customer_message,
        "requires_approval": requires_approval,
        "rejected": rejected,
        "rejection_reason": rejection_reason,
        "approval_reason": "; ".join(approval_reasons) if approval_reasons else None,
        "business_reason": action.get("business_reason") or (
            "; ".join(business_reasons) if business_reasons else policy["guidance"]
        ),
        "risk_level": action.get("risk_level", risk),
        "alternatives": alternatives or [],
        "policy_outcome": "rejected" if rejected else (
            "needs_approval" if requires_approval else "auto_approved"
        ),
    }


def apply_policy(action: dict, category: str, collected_data: dict | None = None) -> dict:
    """Backward-compatible wrapper used by workflow and tests."""
    ticket = (collected_data or {}).get("ticket")
    return evaluate_policy(action, category, ticket)
