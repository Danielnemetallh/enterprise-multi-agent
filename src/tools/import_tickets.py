"""
CSV ticket importer — loads external support datasets into the runtime store.

Usage:
    python src/tools/import_tickets.py --csv <path> --mapping <mapping.json> [--force]
"""

import argparse
import json
import logging
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.db_tools import (
    bulk_insert_tickets,
    clear_imported_tickets,
    create_database,
    ensure_db,
)
from src.tools.ticket_schema import (
    normalize_category,
    normalize_status,
    replace_product_placeholder,
    validate_csv_headers,
)

logger = logging.getLogger(__name__)

DEFAULT_MAPPING_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "mappings", "kaggle_support.json"
)


def load_mapping(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _get_value(row: pd.Series, column_name: str | None) -> str | None:
    if not column_name or column_name not in row.index:
        return None
    value = row[column_name]
    if pd.isna(value):
        return None
    return str(value).strip()


def _parse_rating(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_ticket_row(row: pd.Series, mapping: dict) -> dict:
    """Map one CSV row to a canonical ticket dict."""
    columns = mapping["columns"]
    category_map = mapping.get("category_map", {})
    status_map = mapping.get("status_map", {})
    source_dataset = mapping.get("source_dataset", mapping.get("name", "imported"))

    product = _get_value(row, columns.get("product"))
    subject = replace_product_placeholder(_get_value(row, columns.get("subject")), product)
    description = replace_product_placeholder(
        _get_value(row, columns.get("description")),
        product,
    )

    raw_category = _get_value(row, columns.get("category"))
    category, category_raw = normalize_category(raw_category, category_map)
    status = normalize_status(_get_value(row, columns.get("status")), status_map)

    return {
        "ticket_id": _get_value(row, columns.get("ticket_id")) or f"import-{row.name}",
        "customer_name": _get_value(row, columns.get("customer_name")) or "Unknown",
        "customer_email": _get_value(row, columns.get("customer_email")) or f"import-{row.name}@example.com",
        "category": category,
        "subject": subject or "No subject",
        "description": description or "",
        "status": status,
        "priority": _get_value(row, columns.get("priority")),
        "product": product,
        "channel": _get_value(row, columns.get("channel")),
        "resolution": _get_value(row, columns.get("resolution")),
        "satisfaction_rating": _parse_rating(_get_value(row, columns.get("satisfaction_rating"))),
        "source_dataset": source_dataset,
        "category_raw": category_raw or raw_category,
        "processed_at": None,
        "created_at": _get_value(row, columns.get("created_at")),
    }


def import_tickets_from_csv(
    csv_path: str,
    mapping_path: str,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    """Import tickets from CSV using a column mapping profile."""
    ensure_db()
    mapping = load_mapping(mapping_path)
    source_dataset = mapping.get("source_dataset", mapping.get("name", "imported"))

    df = pd.read_csv(csv_path)
    validate_csv_headers(list(df.columns))

    if limit:
        df = df.head(limit)

    if force:
        deleted = clear_imported_tickets(source_dataset)
        logger.info("Removed %s existing tickets for dataset '%s'", deleted, source_dataset)

    tickets = [normalize_ticket_row(row, mapping) for _, row in df.iterrows()]
    imported = bulk_insert_tickets(tickets)

    return {
        "imported": imported,
        "source_dataset": source_dataset,
        "csv_path": csv_path,
        "mapping": mapping.get("name", os.path.basename(mapping_path)),
    }


def main() -> None:
    from src.tools.logger import setup_logging

    setup_logging()

    parser = argparse.ArgumentParser(description="Import support tickets from CSV")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument(
        "--mapping",
        default=DEFAULT_MAPPING_PATH,
        help="Path to mapping JSON profile",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing imported tickets")
    parser.add_argument("--limit", type=int, default=None, help="Import only first N rows")
    parser.add_argument("--init-db", action="store_true", help="Create empty runtime DB before import")
    args = parser.parse_args()

    if args.init_db:
        create_database(force=True)

    result = import_tickets_from_csv(args.csv, args.mapping, force=args.force, limit=args.limit)
    print(
        f"Imported {result['imported']} tickets from '{result['csv_path']}' "
        f"using mapping '{result['mapping']}'"
    )


if __name__ == "__main__":
    main()
