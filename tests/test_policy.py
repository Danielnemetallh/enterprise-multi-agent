"""Tests for deterministic policy enforcement."""
from src.tools.policy import evaluate_policy


def _ticket(priority: str = "Low") -> dict:
    return {"priority": priority}


class TestPolicy:
    def test_discount_over_15_requires_approval(self):
        action = {
            "action_type": "offer_discount",
            "discount_percent": 20,
            "customer_message": "We can offer you a 20% discount.",
        }
        result = evaluate_policy(action, "refund_request", _ticket())
        assert result["requires_approval"] is True
        assert "15%" in result["approval_reason"]

    def test_cancellation_requires_approval(self):
        action = {
            "action_type": "process_cancellation",
            "discount_percent": 0,
            "customer_message": "We will process your cancellation.",
        }
        result = evaluate_policy(action, "cancellation_request", _ticket())
        assert result["requires_approval"] is True
        assert "Cancellation" in result["approval_reason"]

    def test_small_discount_auto_execute(self):
        action = {
            "action_type": "offer_discount",
            "discount_percent": 10,
            "customer_message": "We can offer you a 10% discount.",
        }
        result = evaluate_policy(action, "refund_request", _ticket("Low"))
        assert result["requires_approval"] is False
        assert result["policy_outcome"] == "auto_approved"

    def test_high_priority_discount_requires_approval(self):
        action = {
            "action_type": "offer_discount",
            "discount_percent": 10,
            "customer_message": "We can offer you a 10% discount.",
        }
        result = evaluate_policy(action, "refund_request", _ticket("High"))
        assert result["requires_approval"] is True

    def test_send_apology_auto_execute(self):
        action = {
            "action_type": "send_apology",
            "discount_percent": 0,
            "customer_message": "We apologize for the inconvenience.",
        }
        result = evaluate_policy(action, "technical_issue", _ticket())
        assert result["requires_approval"] is False

    def test_disallowed_action_rejected(self):
        action = {
            "action_type": "process_cancellation",
            "discount_percent": 0,
            "customer_message": "We will cancel your plan.",
        }
        result = evaluate_policy(action, "technical_issue", _ticket())
        assert result["rejected"] is True
        assert result["policy_outcome"] == "rejected"

    def test_policy_fields_present(self):
        action = {
            "action_type": "provide_information",
            "discount_percent": 0,
            "customer_message": "Here is the requested information.",
        }
        result = evaluate_policy(action, "product_inquiry", _ticket())
        assert "action_type" in result
        assert "customer_message" in result
        assert "risk_level" in result
