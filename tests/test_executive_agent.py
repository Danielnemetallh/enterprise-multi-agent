"""Tests for the executive agent with mocked LLM calls."""
from unittest.mock import patch

from src.agents.executive_agent import run_executive


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
            "subject": "Your refund request",
            "customer_message": "We can offer you a 10% discount.",
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
    def test_fallback_on_parse_error(self, mock_llm):
        mock_llm.return_value = "not json"
        result = run_executive("product_inquiry", {"ticket": _ticket()})
        assert result["action_type"] == "provide_information"
        assert result["discount_percent"] == 0

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_markdown_code_block(self, mock_llm):
        mock_llm.return_value = """```json
{
    "action_type": "provide_information",
    "discount_percent": 0,
    "subject": "Your inquiry",
    "customer_message": "We will follow up shortly.",
    "business_reason": "Standard information response"
}
```"""
        result = run_executive("product_inquiry", {"ticket": _ticket()})
        assert result["action_type"] == "provide_information"

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_defaults_applied_when_missing(self, mock_llm):
        mock_llm.return_value = '{"action_type": "offer_discount"}'
        result = run_executive("billing_inquiry", {"ticket": _ticket()})
        assert result["discount_percent"] == 0
        assert result["subject"]
        assert result["customer_message"]

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_fallback_on_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        result = run_executive("billing_inquiry", {"ticket": _ticket()})
        assert result["action_type"] == "provide_information"
        assert result["discount_percent"] == 0

    @patch("src.agents.executive_agent.call_llm_safe")
    def test_prompt_receives_ticket_text(self, mock_llm):
        mock_llm.return_value = """{
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Your inquiry",
            "customer_message": "Thanks for your question.",
            "business_reason": "Product inquiry"
        }"""
        run_executive("product_inquiry", {"ticket": _ticket(
            subject="Need API docs",
            description="Where can I find the API documentation?",
        )})
        prompt = mock_llm.call_args[0][0]
        assert "Need API docs" in prompt
        assert "Where can I find the API documentation?" in prompt
