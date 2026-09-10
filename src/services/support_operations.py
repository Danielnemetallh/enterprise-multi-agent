"""Backend operations for queue processing and resumable human review."""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.graph.workflow import build_graph
from src.tools import db_tools
from src.tools.case_file import build_case_file, customer_draft_is_clean, new_run_id

TERMINAL_STATUSES = {"completed", "rejected", "failed"}


def list_ticket_queue() -> list[dict]:
    return db_tools.query_open_tickets()


def _initial_state(run_id: str, ticket: dict) -> dict:
    return {
        "input": str(ticket["id"]),
        "run_id": run_id,
        "ticket": ticket,
        "classification": "",
        "triage_source": "",
        "collected_data": {},
        "proposed_action": {},
        "approval": "pending",
        "workflow_trace": [],
        "finalization_result": "",
    }


def _invoke_graph(run_id: str, graph_input) -> dict:
    connection = sqlite3.connect(db_tools.DB_PATH, check_same_thread=False)
    try:
        graph = build_graph(checkpointer=SqliteSaver(connection))
        return graph.invoke(graph_input, config={"configurable": {"thread_id": run_id}})
    finally:
        connection.close()


def _persist_result(run_id: str, result: dict) -> dict:
    action = result.get("proposed_action") or {}
    if result.get("__interrupt__"):
        status = "awaiting_review"
        approval_status = "pending"
    elif action.get("rejected"):
        status = "failed"
        approval_status = "not_required"
    elif result.get("approval") == "rejected":
        status = "rejected"
        approval_status = "rejected"
    else:
        status = "completed"
        approval_status = result.get("approval", "not_required")

    case_file = build_case_file(
        run_id=run_id,
        result=result,
        workflow_trace=result.get("workflow_trace", []),
        finalization_result=result.get("finalization_result", "Awaiting review"),
    )
    review = db_tools.get_workflow_review(run_id)
    if review:
        case_file["human_review"] = review
    db_tools.update_workflow_run(
        run_id,
        status=status,
        approval_status=approval_status,
        state={key: value for key, value in result.items() if key != "__interrupt__"},
        case_file=case_file,
    )
    return get_run(run_id)


def start_ticket_run(ticket_id: int) -> dict:
    ticket = db_tools.query_ticket_by_id(int(ticket_id))
    if ticket is None:
        raise LookupError(f"Ticket {ticket_id} was not found")
    existing = db_tools.find_existing_ticket_run(ticket["id"])
    if existing:
        return existing

    run_id = new_run_id()
    db_tools.create_workflow_run(run_id, ticket["id"])
    try:
        result = _invoke_graph(run_id, _initial_state(run_id, ticket))
        return _persist_result(run_id, result)
    except Exception as exc:
        db_tools.update_workflow_run(
            run_id,
            status="failed",
            approval_status="pending",
            error_message=str(exc),
        )
        return get_run(run_id)


def list_pending_reviews() -> list[dict]:
    return db_tools.list_workflow_runs(status="awaiting_review")


def review_run(run_id: str, command: dict) -> dict:
    run = get_run(run_id)
    if run is None:
        raise LookupError(f"Run {run_id} was not found")
    if run["status"] in TERMINAL_STATUSES:
        existing_review = db_tools.get_workflow_review(run_id)
        if existing_review and _same_review(existing_review, command):
            return run
        raise ValueError(f"Run {run_id} is already {run['status']}")
    if run["status"] != "awaiting_review":
        raise ValueError(f"Run {run_id} is not awaiting review")

    decision = command.get("decision")
    reviewer = str(command.get("reviewer") or "").strip()
    notes = str(command.get("notes") or "").strip() or None
    edited_draft = str(command.get("edited_draft") or "").strip() or None
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be 'approve' or 'reject'")
    if not reviewer:
        raise ValueError("Reviewer identity is required")
    if edited_draft and not customer_draft_is_clean(edited_draft):
        raise ValueError("Edited customer draft exposes internal policy terms")

    existing_review = db_tools.get_workflow_review(run_id)
    normalized_command = {
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes,
        "edited_draft": edited_draft,
    }
    if existing_review and not _same_review(existing_review, normalized_command):
        raise ValueError(f"Run {run_id} already has a different review")
    if existing_review is None:
        db_tools.save_workflow_review(run_id, **normalized_command)
    resume = {
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes,
        "edited_draft": edited_draft,
    }
    try:
        return _persist_result(run_id, _invoke_graph(run_id, Command(resume=resume)))
    except Exception as exc:
        db_tools.update_workflow_run(
            run_id,
            status="failed",
            approval_status="pending",
            error_message=str(exc),
        )
        return get_run(run_id)


def _same_review(existing: dict, command: dict) -> bool:
    return (
        existing["decision"] == command.get("decision")
        and existing["reviewer"] == str(command.get("reviewer") or "").strip()
        and (existing.get("notes") or None) == (str(command.get("notes") or "").strip() or None)
        and (existing.get("edited_draft") or None)
        == (str(command.get("edited_draft") or "").strip() or None)
    )


def get_run(run_id: str) -> dict | None:
    run = db_tools.get_workflow_run(run_id)
    if run:
        run["review"] = db_tools.get_workflow_review(run_id)
    return run
