"""
Company-style case file output for support agent runs.
Separates internal operational report from customer-facing draft.
"""

from datetime import datetime
import uuid


def new_run_id() -> str:
    return f"RUN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def summarize_evidence(ticket: dict, workflow_trace: list[str]) -> list[str]:
    evidence = []
    if ticket:
        evidence.append(
            f"Ticket {ticket.get('ticket_id', '-')} | "
            f"Category: {ticket.get('category', '-')} | "
            f"Priority: {ticket.get('priority', '-')}"
        )
        if ticket.get("product"):
            evidence.append(f"Product: {ticket['product']}")
        if ticket.get("channel"):
            evidence.append(f"Channel: {ticket['channel']}")
        if ticket.get("subject"):
            evidence.append(f"Subject reviewed: {ticket['subject']}")
        if ticket.get("description"):
            evidence.append(f"Description reviewed: {ticket['description'][:120]}")
    if workflow_trace:
        evidence.append(f"Workflow steps recorded: {len(workflow_trace)}")
    if not evidence:
        evidence.append("No additional evidence collected")
    return evidence


def build_case_file(
    run_id: str,
    result: dict,
    workflow_trace: list[str],
    execution_result: str,
) -> dict:
    """Build structured case file from final workflow state."""
    ticket = result.get("ticket") or {}
    action = result.get("proposed_action") or {}
    triage_source = result.get("triage_source", "unknown")

    policy_review = {
        "outcome": action.get("policy_outcome", "unknown"),
        "requires_approval": action.get("requires_approval", False),
        "approval_reason": action.get("approval_reason"),
        "rejection_reason": action.get("rejection_reason"),
        "business_reason": action.get("business_reason"),
        "risk_level": action.get("risk_level", "low"),
    }

    return {
        "run_id": run_id,
        "dataset": ticket.get("source_dataset", "unknown"),
        "ticket_summary": {
            "ticket_id": ticket.get("ticket_id"),
            "internal_id": ticket.get("id"),
            "category": result.get("classification"),
            "priority": ticket.get("priority"),
            "status": ticket.get("status"),
            "subject": ticket.get("subject"),
            "customer_name": ticket.get("customer_name"),
            "customer_email": ticket.get("customer_email"),
            "product": ticket.get("product"),
            "channel": ticket.get("channel"),
        },
        "triage_decision": {
            "classification": result.get("classification"),
            "source": triage_source,
        },
        "evidence": summarize_evidence(ticket, workflow_trace),
        "recommended_action": {
            "action_type": action.get("action_type"),
            "discount_percent": action.get("discount_percent", 0),
            "subject": action.get("subject"),
            "alternatives": action.get("alternatives", []),
        },
        "policy_review": policy_review,
        "approval_status": result.get("approval", "pending"),
        "execution_result": execution_result,
        "customer_draft": action.get("customer_message", ""),
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }


def format_case_file(case: dict) -> str:
    """Render case file for console output."""
    summary = case["ticket_summary"]
    triage = case["triage_decision"]
    action = case["recommended_action"]
    policy = case["policy_review"]

    lines = [
        "=" * 70,
        " CASE FILE",
        "=" * 70,
        f" Run ID:           {case['run_id']}",
        f" Dataset:          {case['dataset']}",
        f" Completed:        {case['completed_at']}",
        "",
        " TICKET SUMMARY",
        "-" * 70,
        f" Ticket ID:        {summary.get('ticket_id', '-')}",
        f" Internal ID:      {summary.get('internal_id', '-')}",
        f" Category:         {summary.get('category', '-')}",
        f" Priority:         {summary.get('priority', '-')}",
        f" Status:           {summary.get('status', '-')}",
        f" Customer:         {summary.get('customer_name', '-')} <{summary.get('customer_email', '-')}>",
        f" Subject:          {summary.get('subject', '-')}",
        f" Product:          {summary.get('product', '-')}",
        f" Channel:          {summary.get('channel', '-')}",
        "",
        " TRIAGE DECISION",
        "-" * 70,
        f" Classification:   {triage.get('classification', '-')}",
        f" Source:           {triage.get('source', '-')}",
        "",
        " EVIDENCE",
        "-" * 70,
    ]
    for item in case["evidence"]:
        lines.append(f"  - {item}")

    lines.extend([
        "",
        " RECOMMENDED ACTION",
        "-" * 70,
        f" Action Type:      {action.get('action_type', '-')}",
        f" Discount:         {action.get('discount_percent', 0)}%",
        f" Subject:          {action.get('subject', '-')}",
    ])
    if action.get("alternatives"):
        lines.append(f" Alternatives:     {', '.join(action['alternatives'])}")

    lines.extend([
        "",
        " POLICY REVIEW",
        "-" * 70,
        f" Outcome:          {policy.get('outcome', '-')}",
        f" Requires Approval:{policy.get('requires_approval')}",
        f" Approval Reason:  {policy.get('approval_reason') or '-'}",
        f" Rejection Reason: {policy.get('rejection_reason') or '-'}",
        f" Business Reason:  {policy.get('business_reason') or '-'}",
        f" Risk Level:       {policy.get('risk_level', '-')}",
        "",
        " APPROVAL STATUS",
        "-" * 70,
        f" Status:           {case['approval_status']}",
        "",
        " EXECUTION RESULT",
        "-" * 70,
        f" Result:           {case['execution_result']}",
        "",
        " CUSTOMER DRAFT",
        "-" * 70,
        f" {case['customer_draft']}",
        "=" * 70,
    ])
    return "\n".join(lines)


def customer_draft_is_clean(customer_draft: str) -> bool:
    """Customer draft must not expose internal policy or LLM labels."""
    forbidden = (
        "policy",
        "llm",
        "requires_approval",
        "risk_level",
        "auto_approved",
        "needs_approval",
    )
    lower = customer_draft.lower()
    return not any(word in lower for word in forbidden)
