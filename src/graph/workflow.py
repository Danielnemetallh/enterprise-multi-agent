"""Resumable SupportFlow graph: triage, proposal, policy, review, finalization."""

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.agents.executive_agent import run_executive
from src.agents.triage_agent import classify_ticket_smart
from src.tools.case_file import customer_draft_is_clean
from src.tools.db_tools import mark_ticket_processed, query_open_tickets


class AgentState(TypedDict):
    input: str
    run_id: str
    ticket: dict | None
    classification: str
    triage_source: str
    collected_data: dict
    proposed_action: dict
    approval: str
    workflow_trace: list[str]
    finalization_result: str


def _append_trace(state: AgentState, step: str) -> list[str]:
    return [*state.get("workflow_trace", []), step]


def triage_agent(state: AgentState) -> AgentState:
    ticket = state.get("ticket")
    if ticket is None:
        tickets = query_open_tickets()
        if not tickets:
            raise LookupError("No open ticket is available")
        ticket = tickets[0]

    classification, triage_source = classify_ticket_smart(ticket)
    return {
        **state,
        "classification": classification,
        "ticket": ticket,
        "triage_source": triage_source,
        "workflow_trace": _append_trace(
            state, f"Triage -> {classification} ({triage_source})"
        ),
    }


def resolution_agent(state: AgentState) -> AgentState:
    ticket = state.get("ticket") or {}
    action = run_executive(state["classification"], {"ticket": ticket})
    trace = _append_trace(
        state,
        f"Resolution -> {action.get('action_type')} ({action.get('discount_percent', 0)}%)",
    )
    trace.append(
        f"Policy -> {action.get('policy_outcome', 'unknown')} "
        f"({action.get('approval_reason') or action.get('rejection_reason') or 'no policy trigger'})"
    )
    return {
        **state,
        "proposed_action": action,
        "collected_data": {"ticket": ticket},
        "workflow_trace": trace,
    }


def human_review(state: AgentState) -> AgentState:
    action = state["proposed_action"]
    review = interrupt(
        {
            "run_id": state["run_id"],
            "ticket": state.get("ticket"),
            "proposed_action": action,
            "approval_reason": action.get("approval_reason"),
        }
    )
    decision = review.get("decision")
    if decision not in {"approve", "reject"}:
        raise ValueError("Review decision must be 'approve' or 'reject'")

    edited_draft = review.get("edited_draft")
    if edited_draft:
        if not customer_draft_is_clean(edited_draft):
            raise ValueError("Edited customer draft exposes internal policy terms")
        action = {**action, "customer_message": edited_draft.strip()}

    approval = "approved" if decision == "approve" else "rejected"
    return {
        **state,
        "proposed_action": action,
        "approval": approval,
        "workflow_trace": _append_trace(state, f"Review -> {approval}"),
    }


def finalize_action(state: AgentState) -> AgentState:
    action = state["proposed_action"]
    ticket = state.get("ticket") or {}
    if action.get("rejected"):
        return {
            **state,
            "finalization_result": "Proposal rejected by deterministic policy",
            "workflow_trace": _append_trace(state, "Finalization -> policy rejected"),
        }
    if state["approval"] == "rejected":
        return {
            **state,
            "finalization_result": "Proposal rejected by reviewer",
            "workflow_trace": _append_trace(state, "Finalization -> reviewer rejected"),
        }

    ticket_id = ticket.get("id")
    if not ticket_id:
        raise ValueError("Finalization requires a ticket id")
    mark_ticket_processed(ticket_id)
    approval = "approved" if action.get("requires_approval") else "not_required"
    return {
        **state,
        "approval": approval,
        "finalization_result": f"Ticket #{ticket_id} finalized locally",
        "workflow_trace": _append_trace(state, "Finalization -> completed"),
    }


def needs_approval(state: AgentState) -> Literal["human_review", "finalize_action"]:
    action = state["proposed_action"]
    if action.get("rejected") or not action.get("requires_approval", False):
        return "finalize_action"
    return "human_review"


def build_graph(checkpointer=None):
    workflow = StateGraph(AgentState)
    workflow.add_node("triage_agent", triage_agent)
    workflow.add_node("resolution_agent", resolution_agent)
    workflow.add_node("human_review", human_review)
    workflow.add_node("finalize_action", finalize_action)
    workflow.set_entry_point("triage_agent")
    workflow.add_edge("triage_agent", "resolution_agent")
    workflow.add_conditional_edges(
        "resolution_agent",
        needs_approval,
        {"human_review": "human_review", "finalize_action": "finalize_action"},
    )
    workflow.add_edge("human_review", "finalize_action")
    workflow.add_edge("finalize_action", END)
    return workflow.compile(checkpointer=checkpointer)
