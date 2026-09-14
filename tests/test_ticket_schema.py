"""Tests for ticket normalization helpers."""
from src.tools.ticket_schema import (
    normalize_category,
    normalize_status,
    replace_product_placeholder,
    should_use_llm_for_triage,
    validate_csv_headers,
)


class TestNormalization:
    def test_category_mapping(self):
        category, raw = normalize_category("Cancellation request")
        assert category == "cancellation_request"
        assert raw == "Cancellation request"

    def test_unknown_category_is_preserved_without_guessing(self):
        category, raw = normalize_category("Account setup")
        assert category == "unknown"
        assert raw == "Account setup"

    def test_status_mapping(self):
        assert normalize_status("Open") == "open"
        assert normalize_status("Pending Customer Response") == "pending"
        assert normalize_status("Closed") == "closed"

    def test_placeholder_replacement(self):
        text = "Price for {product_purchased}?"
        assert replace_product_placeholder(text, "Cloud Storage Pro") == "Price for Cloud Storage Pro?"

    def test_metadata_triage_skips_llm(self):
        ticket = {
            "category": "product_inquiry",
            "category_raw": "Product inquiry",
            "priority": "Low",
        }
        assert should_use_llm_for_triage(ticket) is False

    def test_unknown_category_triggers_llm(self):
        ticket = {"category": "product_inquiry", "category_raw": "Account setup"}
        assert should_use_llm_for_triage(ticket) is True

    def test_high_risk_cancellation_triggers_llm(self):
        ticket = {
            "category": "cancellation_request",
            "category_raw": "Cancellation request",
            "priority": "High",
        }
        assert should_use_llm_for_triage(ticket) is True

    def test_validate_csv_headers(self):
        headers = [
            "Ticket ID",
            "Customer Name",
            "Customer Email",
            "Product Purchased",
            "Ticket Type",
            "Ticket Subject",
            "Ticket Description",
            "Ticket Status",
            "Ticket Priority",
            "Ticket Channel",
            "Resolution",
            "Customer Satisfaction Rating",
        ]
        validate_csv_headers(headers)

    def test_validate_csv_headers_missing(self):
        try:
            validate_csv_headers(["Ticket ID"])
            assert False, "Expected ValueError"
        except ValueError as exc:
            assert "missing required headers" in str(exc)
