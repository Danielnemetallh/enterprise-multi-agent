"""Tests for case file output."""
from src.tools.case_file import build_case_file, customer_draft_is_clean, format_case_file


class TestCaseFile:
    def test_case_file_contains_required_sections(self):
        result = {
            "ticket": {
                "id": 1,
                "ticket_id": "T-1001",
                "source_dataset": "kaggle_customer_support",
                "subject": "Pricing question",
                "priority": "Low",
                "status": "open",
                "product": "Cloud Storage Pro",
                "channel": "Email",
                "customer_name": "Anna",
                "customer_email": "anna@example.com",
                "description": "What does the annual plan cost?",
            },
            "classification": "product_inquiry",
            "triage_source": "metadata",
            "collected_data": {"ticket": {}},
            "proposed_action": {
                "action_type": "offer_discount",
                "discount_percent": 10,
                "subject": "Your offer",
                "customer_message": "We can offer you a 10% discount.",
                "requires_approval": False,
                "approval_reason": None,
                "business_reason": "Product inquiry",
                "risk_level": "low",
                "policy_outcome": "auto_approved",
                "alternatives": [],
            },
            "approval": "approved",
        }
        case = build_case_file(
            run_id="RUN-TEST-001",
            result=result,
            workflow_trace=["Triage -> product_inquiry (metadata)", "Execute -> completed"],
            execution_result="Ticket #1 processed successfully",
        )

        assert case["run_id"] == "RUN-TEST-001"
        assert case["dataset"] == "kaggle_customer_support"
        assert case["triage_decision"]["classification"] == "product_inquiry"
        assert case["policy_review"]["requires_approval"] is False
        assert case["customer_draft"] == "We can offer you a 10% discount."

        rendered = format_case_file(case)
        assert "CASE FILE" in rendered
        assert "TICKET SUMMARY" in rendered
        assert "TRIAGE DECISION" in rendered
        assert "POLICY REVIEW" in rendered
        assert "CUSTOMER DRAFT" in rendered
        assert "policy" not in case["customer_draft"].lower()

    def test_customer_draft_is_clean(self):
        assert customer_draft_is_clean("Thank you for your request.") is True
        assert customer_draft_is_clean("This action requires_approval.") is False
