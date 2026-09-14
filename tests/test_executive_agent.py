"""Tests for the executive agent with mocked LLM calls."""
from unittest.mock import patch

import pytest

from src.agents.executive_agent import ProposalValidationError, ProviderFailure, run_executive


def _ticket(**overrides):
    base = {
        "id": 1,
        "ticket_id": "T-1001",
        "customer_name": "Max Test",
        "customer_email": "max@example.com",
        "priority": "Low",
        "product": "Cloud Storage Pro",
        "subject": "Pricing question",
        "description": "What does the annual plan cost?",
    }
    base.update(overrides)
    return base


class TestRunExecutive:
    @patch("src.agents.executive_agent.call_llm_safe")
    def test_refund_request_creates_discount_offer(self, mock_llm):
        mock_llm.return_value = """{
            "action_type": "offer_discount",
            "discount_percent": 10,
            "subject": "Ihre Erstattungsanfrage",
            "customer_message": "Wir können Ihnen einen Rabatt von 10 % anbieten.",
            "business_reason": "Partial goodwill offer for refund request"
        }"""
        result = run_executive("refund_request", {"ticket": _ticket()})
        assert result["action_type"] == "offer_discount"
        assert result["discount_percent"] == 10
        assert result["requires_approval"] is False

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_cancellation_requires_approval(self, mock_llm):
        mock_llm.return_value = """{
            "action_type": "process_cancellation",
            "discount_percent": 0,
            "subject": "Cancellation request received",
            "customer_message": "We will process your cancellation request.",
            "business_reason": "Customer requested cancellation"
        }"""
        result = run_executive("cancellation_request", {"ticket": _ticket(priority="High")})
        assert result["action_type"] == "process_cancellation"
        assert result["requires_approval"] is True

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_parse_error_fails_the_run(self, mock_llm):
        mock_llm.return_value = "not json"
        with pytest.raises(ProposalValidationError):
            run_executive("product_inquiry", {"ticket": _ticket()})

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_markdown_code_block(self, mock_llm):
        mock_llm.return_value = """```json
{
    "action_type": "provide_information",
    "discount_percent": 0,
            "subject": "Ihre Anfrage",
            "customer_message": "Wir melden uns in Kürze bei Ihnen.",
    "business_reason": "Standard information response"
}
```"""
        result = run_executive("product_inquiry", {"ticket": _ticket()})
        assert result["action_type"] == "provide_information"

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_missing_required_fields_fail_validation(self, mock_llm):
        mock_llm.return_value = '{"action_type": "offer_discount"}'
        with pytest.raises(ProposalValidationError):
            run_executive("billing_inquiry", {"ticket": _ticket()})

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_provider_failure_is_visible(self, mock_llm):
        mock_llm.return_value = None
        with pytest.raises(ProviderFailure):
            run_executive("billing_inquiry", {"ticket": _ticket()})

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_customer_draft_cannot_expose_policy_terms(self, mock_llm):
        mock_llm.return_value = """{
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Ihre Anfrage",
            "customer_message": "Unsere Richtlinie erfordert eine Freigabe."
        }"""
        with pytest.raises(ProposalValidationError):
            run_executive("product_inquiry", {"ticket": _ticket()})

    @patch("src.agents.executive_agent.call_llm_safe")
    @pytest.mark.parametrize("discount", [-1, 31, "NaN", "Infinity"])
    def test_invalid_discounts_fail_validation(self, mock_llm, discount):
        mock_llm.return_value = (
            '{"action_type":"offer_discount","discount_percent":'
            + (f'"{discount}"' if isinstance(discount, str) else str(discount))
            + ',"subject":"Angebot","customer_message":"Wir bieten Ihnen einen Rabatt an."}'
        )
        with pytest.raises(ProposalValidationError):
            run_executive("refund_request", {"ticket": _ticket()})

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_prompt_receives_ticket_text(self, mock_llm):
        mock_llm.return_value = """{
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Ihre Anfrage",
            "customer_message": "Vielen Dank für Ihre Frage.",
            "business_reason": "Product inquiry"
        }"""
        run_executive("product_inquiry", {"ticket": _ticket(
            subject="Need API docs",
            description="Where can I find the API documentation?",
        )})
        prompt = mock_llm.call_args[0][0]
        assert "Need API docs" in prompt
        assert "Where can I find the API documentation?" in prompt
