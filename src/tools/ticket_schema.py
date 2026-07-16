"""
Canonical support-ticket normalization for imported datasets.
"""

INTERNAL_CATEGORIES = (
    "technical_issue",
    "refund_request",
    "cancellation_request",
    "product_inquiry",
    "billing_inquiry",
)

INTERNAL_STATUSES = ("open", "pending", "closed")

DEFAULT_CATEGORY_MAP = {
    "cancellation request": "cancellation_request",
    "technical issue": "technical_issue",
    "refund request": "refund_request",
    "product inquiry": "product_inquiry",
    "billing inquiry": "billing_inquiry",
}

DEFAULT_STATUS_MAP = {
    "open": "open",
    "pending customer response": "pending",
    "closed": "closed",
}

HIGH_RISK_PRIORITIES = {"high", "critical", "urgent"}

REQUIRED_CSV_HEADERS = (
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
)


def normalize_category(raw: str | None, category_map: dict | None = None) -> tuple[str, str | None]:
    """Map external category to internal category. Returns (category, raw_category)."""
    if not raw or not str(raw).strip():
        return "product_inquiry", None

    raw_str = str(raw).strip()
    mapping = {k.lower(): v for k, v in (category_map or DEFAULT_CATEGORY_MAP).items()}
    normalized = mapping.get(raw_str.lower())
    if normalized:
        return normalized, raw_str
    return "product_inquiry", raw_str


def normalize_status(raw: str | None, status_map: dict | None = None) -> str:
    """Map external status to internal status."""
    if not raw or not str(raw).strip():
        return "open"

    raw_str = str(raw).strip()
    mapping = {k.lower(): v for k, v in (status_map or DEFAULT_STATUS_MAP).items()}
    return mapping.get(raw_str.lower(), "open")


def replace_product_placeholder(text: str | None, product: str | None) -> str:
    """Replace {product_purchased} placeholders with the actual product name."""
    if not text:
        return ""
    product_name = (product or "unknown product").strip()
    return str(text).replace("{product_purchased}", product_name)


def is_high_risk_ticket(ticket: dict) -> bool:
    """High-priority cancellation tickets need LLM validation."""
    priority = str(ticket.get("priority", "")).lower()
    classification = ticket.get("category") or ticket.get("classification", "")
    return classification == "cancellation_request" and priority in HIGH_RISK_PRIORITIES


def should_use_llm_for_triage(ticket: dict) -> bool:
    """Decide whether triage needs an LLM call."""
    category = ticket.get("category", "")
    category_raw = ticket.get("category_raw")

    if not category or category not in INTERNAL_CATEGORIES:
        return True

    if category_raw and category_raw.lower() not in DEFAULT_CATEGORY_MAP:
        return True

    if is_high_risk_ticket(ticket):
        return True

    return False


def validate_csv_headers(headers: list[str]) -> None:
    """Raise ValueError when required CSV headers are missing."""
    missing = [header for header in REQUIRED_CSV_HEADERS if header not in headers]
    if missing:
        raise ValueError(
            "CSV import failed: missing required headers: " + ", ".join(missing)
        )
