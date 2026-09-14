"""Behavioral tests for the resumable support-operations boundary."""

from unittest.mock import patch

import pytest

from src.services.support_operations import (
    get_run,
    list_pending_reviews,
    list_ticket_queue,
    review_run,
    start_ticket_run,
)
from src.tools import db_tools


@pytest.fixture
def operations_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_tools, "DB_PATH", str(tmp_path / "supportflow.db"))
    db_tools.create_database(force=True)
    db_tools.bulk_insert_tickets([
        {
            "ticket_id": "T-100",
            "customer_name": "Anna Beispiel",
            "customer_email": "anna@example.com",
            "category": "product_inquiry",
            "category_raw": "Product inquiry",
            "subject": "Preise",
            "description": "Was kostet das Jahresabo?",
            "status": "open",
            "priority": "Low",
            "source_dataset": "synthetic",
            "created_at": "2026-01-01T10:00:00",
        }
    ])
    return str(tmp_path / "supportflow.db")


def _proposal(requires_approval=False):
    return {
        "action_type": "provide_information",
        "discount_percent": 0,
        "subject": "Ihre Anfrage",
        "customer_message": "Vielen Dank für Ihre Anfrage. Wir senden Ihnen die Preisinformationen.",
        "requires_approval": requires_approval,
        "rejected": False,
        "policy_outcome": "needs_approval" if requires_approval else "auto_approved",
        "approval_reason": "Manuelle Prüfung erforderlich" if requires_approval else None,
        "risk_level": "medium" if requires_approval else "low",
        "decision_source": "deterministic_policy",
        "policy_rules": [],
        "alternatives": [],
    }


@patch("src.graph.workflow.classify_ticket_smart", return_value=("product_inquiry", "metadata"))
@patch("src.graph.workflow.run_executive", return_value=_proposal(False))
def test_auto_approved_run_finalizes_once(mock_resolution, mock_triage, operations_db):
    queued = list_ticket_queue()
    assert [ticket["ticket_id"] for ticket in queued] == ["T-100"]

    run = start_ticket_run(1)
    assert run["status"] == "completed"
    assert run["approval_status"] == "not_required"
    assert db_tools.query_ticket_by_id(1)["processed_at"] is not None
    assert start_ticket_run(1)["run_id"] == run["run_id"]
    assert get_run(run["run_id"])["case_file"]["policy_review"]["decision_source"] == "deterministic_policy"


@patch("src.graph.workflow.classify_ticket_smart", return_value=("product_inquiry", "metadata"))
@patch("src.graph.workflow.run_executive", return_value=_proposal(True))
def test_review_can_resume_approve_and_is_idempotent(mock_resolution, mock_triage, operations_db):
    pending_run = start_ticket_run(1)
    assert pending_run["status"] == "awaiting_review"
    assert [item["run_id"] for item in list_pending_reviews()] == [pending_run["run_id"]]
    assert db_tools.query_ticket_by_id(1)["processed_at"] is None

    completed = review_run(
        pending_run["run_id"],
        {"decision": "approve", "reviewer": "dania", "notes": "Geprüft"},
    )
    assert completed["status"] == "completed"
    assert completed["approval_status"] == "approved"
    assert completed["review"]["reviewer"] == "dania"
    assert completed["case_file"]["human_review"]["notes"] == "Geprüft"
    duplicate = review_run(
        pending_run["run_id"],
        {"decision": "approve", "reviewer": "dania", "notes": "Geprüft"},
    )
    assert duplicate["status"] == "completed"


@patch("src.graph.workflow.classify_ticket_smart", return_value=("product_inquiry", "metadata"))
@patch("src.graph.workflow.run_executive", return_value=_proposal(True))
def test_rejected_run_leaves_ticket_open(mock_resolution, mock_triage, operations_db):
    pending_run = start_ticket_run(1)
    rejected = review_run(
        pending_run["run_id"],
        {"decision": "reject", "reviewer": "reviewer-1", "notes": "Nicht freigegeben"},
    )
    assert rejected["status"] == "rejected"
    assert db_tools.query_ticket_by_id(1)["processed_at"] is None
