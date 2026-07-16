"""Tests for triage agent classification."""
from unittest.mock import patch

from src.agents.triage_agent import classify_ticket, classify_ticket_smart, run_triage


class TestClassifyTicket:
    @patch("src.agents.triage_agent.call_llm_safe")
    def test_product_inquiry(self, mock_llm):
        mock_llm.return_value = "product_inquiry"
        result = classify_ticket("What does it cost?", "I need pricing details.")
        assert result == "product_inquiry"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_technical_issue(self, mock_llm):
        mock_llm.return_value = "technical_issue"
        result = classify_ticket("Outage", "Service was down.")
        assert result == "technical_issue"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_cancellation_request(self, mock_llm):
        mock_llm.return_value = "cancellation_request"
        result = classify_ticket("Cancellation", "I want to cancel.")
        assert result == "cancellation_request"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_fallback_on_unexpected_response(self, mock_llm):
        mock_llm.return_value = "something-else"
        result = classify_ticket("Test", "Test")
        assert result == "product_inquiry"

    @patch("src.agents.triage_agent.call_llm_safe")
    def test_fallback_on_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        result = classify_ticket("Test", "Test")
        assert result == "product_inquiry"


class TestClassifyTicketSmart:
    def test_known_category_uses_metadata(self):
        ticket = {
            "id": 1,
            "category": "product_inquiry",
            "category_raw": "Product inquiry",
            "priority": "Low",
            "subject": "Pricing",
            "description": "What does it cost?",
        }
        result, source = classify_ticket_smart(ticket)
        assert result == "product_inquiry"
        assert source == "metadata"

    @patch("src.agents.triage_agent.classify_ticket")
    def test_unknown_category_uses_llm(self, mock_classify):
        mock_classify.return_value = "billing_inquiry"
        ticket = {
            "id": 2,
            "category": "product_inquiry",
            "category_raw": "Account setup",
            "subject": "Help",
            "description": "I need help",
        }
        result, source = classify_ticket_smart(ticket)
        assert result == "billing_inquiry"
        assert source == "llm"
        mock_classify.assert_called_once()

    @patch("src.agents.triage_agent.classify_ticket")
    def test_high_risk_cancellation_validates_with_llm(self, mock_classify):
        mock_classify.return_value = "cancellation_request"
        ticket = {
            "id": 3,
            "category": "cancellation_request",
            "category_raw": "Cancellation request",
            "priority": "High",
            "subject": "Cancel plan",
            "description": "Please cancel my subscription.",
        }
        result, source = classify_ticket_smart(ticket)
        assert result == "cancellation_request"
        assert source == "llm_validated"


class TestRunTriage:
    @patch("src.agents.triage_agent.classify_ticket_smart")
    def test_classifies_all_tickets(self, mock_classify):
        mock_classify.return_value = ("product_inquiry", "metadata")
        tickets = [
            {"subject": "A", "description": "Message A"},
            {"subject": "B", "description": "Message B"},
        ]
        result = run_triage(tickets)
        assert len(result) == 2
        assert all(t["classification"] == "product_inquiry" for t in result)
