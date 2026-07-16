"""Tests for workflow approval routing logic."""
import pytest

from src.graph.workflow import AgentState, needs_approval


@pytest.fixture
def base_state():
    return AgentState(
        input="",
        run_id="RUN-TEST",
        ticket=None,
        classification="",
        triage_source="",
        collected_data={},
        proposed_action={},
        approval="pending",
        workflow_trace=[],
        execution_result="",
    )


class TestNeedsApproval:
    def test_requires_approval_true_needs_human_review(self, base_state):
        base_state["proposed_action"] = {
            "action_type": "offer_discount",
            "discount_percent": 20,
            "requires_approval": True,
        }
        assert needs_approval(base_state) == "human_review"

    def test_rejected_action_goes_to_execute(self, base_state):
        base_state["proposed_action"] = {
            "action_type": "process_cancellation",
            "rejected": True,
            "requires_approval": True,
        }
        assert needs_approval(base_state) == "execute_action"

    def test_low_risk_action_auto_executes(self, base_state):
        base_state["proposed_action"] = {
            "action_type": "provide_information",
            "discount_percent": 0,
            "requires_approval": False,
        }
        assert needs_approval(base_state) == "execute_action"

    def test_empty_action_dict(self, base_state):
        base_state["proposed_action"] = {}
        assert needs_approval(base_state) == "execute_action"
