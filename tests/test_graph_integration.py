"""Integration tests for the LangGraph workflow."""
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.graph.workflow import build_graph


@pytest.fixture
def mock_ticket():
    return {
        "id": 5,
        "ticket_id": "T-1005",
        "category": "product_inquiry",
        "subject": "Price for Cloud Storage Pro?",
        "description": "What does Cloud Storage Pro cost?",
        "customer_name": "Veit Klemm",
        "customer_email": "veit@test.de",
        "priority": "Low",
        "status": "open",
        "source_dataset": "kaggle_customer_support",
    }


@pytest.fixture(autouse=True)
def mock_ticket_finalization():
    with patch("src.graph.workflow.mark_ticket_processed"):
        yield


def _initial_state():
    return {
        "input": "",
        "run_id": "RUN-TEST",
        "ticket": None,
        "classification": "",
        "triage_source": "",
        "collected_data": {},
        "proposed_action": {},
        "approval": "pending",
        "workflow_trace": [],
        "finalization_result": "",
    }


class TestGraphIntegration:
    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket_smart")
    @patch("src.graph.workflow.run_executive")
    def test_product_inquiry_flow(self, mock_exec, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = ("product_inquiry", "metadata")
        mock_exec.return_value = {
            "action_type": "offer_discount",
            "discount_percent": 10,
            "subject": "Your offer",
            "customer_message": "We can offer you a 10% discount.",
            "requires_approval": False,
            "policy_outcome": "auto_approved",
        }

        graph = build_graph()
        result = graph.invoke(_initial_state())

        assert result["classification"] == "product_inquiry"
        assert result["ticket"] is not None
        assert result["proposed_action"]["action_type"] == "offer_discount"
        assert result["approval"] == "not_required"
        assert result["workflow_trace"]
        mock_exec.assert_called_once()

    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket_smart")
    @patch("src.graph.workflow.run_executive")
    def test_cancellation_flow(self, mock_exec, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = ("cancellation_request", "metadata")
        mock_exec.return_value = {
            "action_type": "process_cancellation",
            "discount_percent": 0,
            "subject": "Cancellation request received",
            "customer_message": "We will process your cancellation.",
            "requires_approval": True,
            "policy_outcome": "needs_approval",
            "approval_reason": "Cancellation requests require human approval",
        }

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "RUN-TEST-CANCEL"}}
        interrupted = graph.invoke(_initial_state(), config=config)
        result = graph.invoke(Command(resume={"decision": "approve"}), config=config)

        assert result["classification"] == "cancellation_request"
        assert result["proposed_action"]["requires_approval"] is True
        assert result["approval"] == "approved"
        assert interrupted["__interrupt__"]

    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket_smart")
    @patch("src.graph.workflow.run_executive")
    def test_billing_inquiry_goes_directly_to_executive(self, mock_exec, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = ("billing_inquiry", "metadata")
        mock_exec.return_value = {
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Billing details",
            "customer_message": "Here is the billing information you requested.",
            "requires_approval": False,
            "policy_outcome": "auto_approved",
        }

        graph = build_graph()
        result = graph.invoke(_initial_state())

        assert result["classification"] == "billing_inquiry"
        assert result["proposed_action"]["action_type"] == "provide_information"

    @patch("src.graph.workflow.query_open_tickets")
    @patch("src.graph.workflow.classify_ticket_smart")
    @patch("src.graph.workflow.run_executive")
    def test_critical_discount_requires_hitl(self, mock_exec, mock_classify, mock_tickets, mock_ticket):
        mock_tickets.return_value = [mock_ticket]
        mock_classify.return_value = ("refund_request", "metadata")
        mock_exec.return_value = {
            "action_type": "offer_discount",
            "discount_percent": 20,
            "subject": "Refund offer",
            "customer_message": "We can offer you a 20% discount.",
            "requires_approval": True,
            "policy_outcome": "needs_approval",
            "approval_reason": "Discount 20% exceeds the 15% policy limit",
        }

        graph = build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "RUN-TEST-DISCOUNT"}}
        interrupted = graph.invoke(_initial_state(), config=config)
        result = graph.invoke(Command(resume={"decision": "approve"}), config=config)

        assert result["proposed_action"]["requires_approval"] is True
        assert interrupted["__interrupt__"]
        assert "Review -> approved" in result["workflow_trace"][-2]
