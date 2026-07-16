"""
Enterprise Multi-Agent System — LangGraph Workflow
====================================================
Nodes:   triage -> executive -> human_review -> execute
Edges:   conditional routing via needs_approval()
State:   AgentState (TypedDict)
LLM:     DeepSeek (via src.tools.llm)
DB:      SQLite ticket store (via src.tools.db_tools)
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.executive_agent import run_executive
from src.agents.triage_agent import classify_ticket_smart
from src.tools.case_file import build_case_file, format_case_file, new_run_id
from src.tools.db_tools import mark_ticket_processed, query_open_tickets
from src.tools.llm import extract_json, get_llm
from src.tools.policy import evaluate_policy

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Shared state flowing through the graph."""

    input: str
    run_id: str
    ticket: dict | None
    classification: str
    triage_source: str
    collected_data: dict
    proposed_action: dict
    approval: str
    workflow_trace: list[str]
    execution_result: str


def _append_trace(state: AgentState, step: str) -> list[str]:
    trace = list(state.get("workflow_trace", []))
    trace.append(step)
    return trace


def triage_agent(state: AgentState) -> AgentState:
    """Agent 1: classify the next open ticket."""
    try:
        tickets = query_open_tickets()
        if not tickets:
            logger.warning("No open tickets found")
            return {
                **state,
                "classification": "product_inquiry",
                "ticket": None,
                "triage_source": "none",
                "workflow_trace": _append_trace(state, "Triage -> no open tickets"),
            }

        ticket = tickets[0]
        if state["input"]:
            requested = state["input"].strip()
            for candidate in tickets:
                if str(candidate["id"]) == requested or candidate.get("ticket_id") == requested:
                    ticket = candidate
                    break

        classification, triage_source = classify_ticket_smart(ticket)
        trace = _append_trace(state, f"Triage -> {classification} ({triage_source})")
        logger.info("Triage: [%s] #%s %s", classification, ticket["id"], ticket["subject"])
        return {
            **state,
            "classification": classification,
            "ticket": ticket,
            "triage_source": triage_source,
            "workflow_trace": trace,
        }
    except Exception as exc:
        logger.error("Triage agent error: %s", exc)
        return {
            **state,
            "classification": "product_inquiry",
            "ticket": None,
            "triage_source": "error",
            "workflow_trace": _append_trace(state, f"Triage -> error: {exc}"),
        }


def executive_agent(state: AgentState) -> AgentState:
    """Agent 2: create a policy-compatible solution proposal."""
    try:
        ticket = state.get("ticket") or {}
        collected_data = {"ticket": ticket}
        action = run_executive(state["classification"], collected_data)
        requires = action.get("requires_approval", False)
        trace = _append_trace(
            state,
            f"Executive -> {action.get('action_type')} ({action.get('discount_percent', 0)}%)",
        )
        trace.append(
            f"Policy -> {action.get('policy_outcome', 'unknown')} "
            f"({action.get('approval_reason') or 'no policy trigger'})"
        )
        return {
            **state,
            "proposed_action": action,
            "collected_data": collected_data,
            "workflow_trace": trace,
        }
    except Exception as exc:
        logger.error("Executive agent error: %s", exc)
        return {
            **state,
            "proposed_action": evaluate_policy(
                {
                    "action_type": "provide_information",
                    "discount_percent": 0,
                    "subject": "Your support request",
                    "customer_message": "We could not process your request at this time.",
                },
                state.get("classification", "product_inquiry"),
                state.get("ticket"),
            ),
            "workflow_trace": _append_trace(state, f"Executive -> error: {exc}"),
        }


def human_review(state: AgentState) -> AgentState:
    """Wait for human approval for critical actions."""
    while True:
        action = state["proposed_action"]

        print("\n APPROVAL REQUIRED\n")
        print(" -------------------------------------")
        print(f"  Action: {action.get('action_type', '?')}")
        print(f"  Discount: {action.get('discount_percent', 0)}%")
        print(f"  Reason: {action.get('approval_reason', '-')}")
        print(f"  Subject: {action.get('subject', '?')}")
        print(f"  Customer Draft: {action.get('customer_message', '?')}")
        print(" -------------------------------------")

        response = input("  Approve action? (yes/no/alternative): ").strip().lower()

        if response in ("yes", "ja"):
            trace = _append_trace(state, "HITL -> approved")
            logger.info("Action approved")
            return {**state, "approval": "approved", "workflow_trace": trace}

        if response in ("no", "nein"):
            trace = _append_trace(state, "HITL -> rejected")
            logger.info("Action rejected")
            return {**state, "approval": "rejected", "workflow_trace": trace}

        if response in ("alternative", "eigen"):
            print("\n  Generating alternative proposal...")
            prompt = f"""The human reviewer rejected this proposed action:
{json.dumps(action, indent=2, ensure_ascii=False)}

Based on the SAME ticket details, suggest a DIFFERENT approach.

Respond with a JSON object:
{{
    "action_type": "offer_discount|send_apology|provide_information|process_cancellation",
    "discount_percent": <number 0-30>,
    "subject": "<short subject in English>",
    "customer_message": "<alternative response in English, max 2 sentences>",
    "business_reason": "<short internal reason>"
}}"""
            try:
                llm = get_llm(temperature=0.3)
                resp = llm.invoke(prompt)
                new_action = extract_json(resp.content)
                new_action.setdefault("action_type", "provide_information")
                new_action.setdefault("discount_percent", 0)
                new_action.setdefault("subject", "Alternative proposal")
                new_action.setdefault(
                    "customer_message",
                    "We have prepared an alternative response for you.",
                )
                new_action = evaluate_policy(
                    new_action,
                    state["classification"],
                    state.get("ticket"),
                )
                state["proposed_action"] = new_action
                logger.info(
                    "Alternative proposal: %s | %s",
                    new_action["action_type"],
                    new_action.get("subject", "?"),
                )
            except Exception as exc:
                logger.error("Alternative proposal failed: %s", exc)
                print(f"  Could not create an alternative proposal: {exc}")
        else:
            print("  Please enter 'yes', 'no', or 'alternative'.")


def execute_action(state: AgentState) -> AgentState:
    """Execute the approved action."""
    action = state["proposed_action"]
    ticket = state.get("ticket") or {}

    if action.get("rejected"):
        result = "Action rejected by policy — nothing executed"
        return {
            **state,
            "execution_result": result,
            "workflow_trace": _append_trace(state, "Execute -> policy rejected"),
        }

    if state["approval"] == "rejected":
        result = "Action rejected by reviewer — nothing executed"
        logger.warning(
            "Action rejected | Type: %s | Discount: %s%% | Customer: %s",
            action.get("action_type", "?"),
            action.get("discount_percent", 0),
            ticket.get("customer_name", "?"),
        )
        return {
            **state,
            "execution_result": result,
            "workflow_trace": _append_trace(state, "Execute -> reviewer rejected"),
        }

    logger.info(
        "Action executed | Type: %s | Discount: %s%% | Customer: %s",
        action.get("action_type", "?"),
        action.get("discount_percent", 0),
        ticket.get("customer_name", "?"),
    )

    ticket_id = ticket.get("id")
    if ticket_id:
        mark_ticket_processed(ticket_id)

    result = (
        f"Ticket #{ticket_id} processed successfully"
        if ticket_id
        else "Action executed successfully"
    )
    return {
        **state,
        "approval": "approved",
        "execution_result": result,
        "workflow_trace": _append_trace(state, "Execute -> completed"),
    }


def needs_approval(state: AgentState) -> Literal["human_review", "execute_action"]:
    action = state["proposed_action"]
    if action.get("rejected"):
        return "execute_action"
    if action.get("requires_approval", False):
        return "human_review"
    return "execute_action"


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("triage_agent", triage_agent)
    workflow.add_node("executive_agent", executive_agent)
    workflow.add_node("human_review", human_review)
    workflow.add_node("execute_action", execute_action)

    workflow.set_entry_point("triage_agent")
    workflow.add_edge("triage_agent", "executive_agent")
    workflow.add_conditional_edges(
        "executive_agent",
        needs_approval,
        {"human_review": "human_review", "execute_action": "execute_action"},
    )
    workflow.add_edge("human_review", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()


if __name__ == "__main__":
    from src.tools.logger import setup_logging

    setup_logging(quiet=True)

    graph = build_graph()
    run_id = new_run_id()

    try:
        result = graph.invoke({
            "input": "",
            "run_id": run_id,
            "ticket": None,
            "classification": "",
            "triage_source": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
            "workflow_trace": [],
            "execution_result": "",
        })

        case = build_case_file(
            run_id=run_id,
            result=result,
            workflow_trace=result.get("workflow_trace", []),
            execution_result=result.get("execution_result", "unknown"),
        )
        print("\n" + format_case_file(case))

    except Exception as exc:
        case = build_case_file(
            run_id=run_id,
            result={
                "ticket": None,
                "classification": "",
                "triage_source": "error",
                "collected_data": {},
                "proposed_action": {},
                "approval": "failed",
            },
            workflow_trace=[f"Workflow failed: {exc}"],
            execution_result=f"Workflow failed: {exc}",
        )
        print("\n" + format_case_file(case))
