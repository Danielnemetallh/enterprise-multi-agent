#!/usr/bin/env python3
"""SupportFlow command-line interface."""

import argparse
import json
import os
import sys

from src.services.support_operations import (
    get_run,
    list_pending_reviews,
    list_ticket_queue,
    review_run,
    start_ticket_run,
)
from src.tools import db_tools
from src.tools.import_tickets import import_tickets_from_csv
from src.tools.llm import call_llm_safe

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTHETIC_CSV = os.path.join(PROJECT_ROOT, "data", "synthetic_support_tickets.csv")
MAPPING_JSON = os.path.join(PROJECT_ROOT, "data", "mappings", "kaggle_support.json")


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="supportflow",
        description="Kontrollierte KI für den Kundenservice",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser("seed", help="Synthetische Demo-Tickets importieren")
    seed.add_argument("--force", action="store_true", help="Vorhandene Demo-Tickets ersetzen")
    commands.add_parser("queue", help="Offene Ticket-Warteschlange anzeigen")

    process = commands.add_parser("process", help="Einen Ticket-Lauf starten")
    process.add_argument("--ticket", required=True, type=int, help="Interne Ticket-ID")
    commands.add_parser("approvals", help="Ausstehende Freigaben anzeigen")

    review = commands.add_parser("review", help="Einen pausierten Lauf prüfen")
    review.add_argument("--run", required=True, dest="run_id")
    review.add_argument("--decision", required=True, choices=("approve", "reject"))
    review.add_argument("--reviewer", default=os.getenv("USERNAME") or "local-reviewer")
    review.add_argument("--notes")
    review.add_argument("--draft", dest="edited_draft")

    show = commands.add_parser("show", help="Einen Lauf und seinen Fallbericht anzeigen")
    show.add_argument("--run", required=True, dest="run_id")

    doctor = commands.add_parser("doctor", help="Lokale Konfiguration prüfen")
    doctor.add_argument("--live", action="store_true", help="Expliziten DeepSeek-Smoke-Test ausführen")
    return parser


def _doctor(live: bool) -> int:
    db_tools.ensure_db()
    result = {
        "python": sys.version.split()[0],
        "database": db_tools.DB_PATH,
        "database_ready": os.path.exists(db_tools.DB_PATH),
        "deepseek_key_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        "live_check": "not_requested",
    }
    if live:
        result["live_check"] = "ok" if call_llm_safe("Antworte ausschließlich mit OK.") else "failed"
    _print_json(result)
    return 0 if result["live_check"] != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "seed":
        if args.force:
            db_tools.create_database(force=True)
        _print_json(import_tickets_from_csv(SYNTHETIC_CSV, MAPPING_JSON, force=False))
    elif args.command == "queue":
        _print_json(list_ticket_queue())
    elif args.command == "process":
        _print_json(start_ticket_run(args.ticket))
    elif args.command == "approvals":
        _print_json(list_pending_reviews())
    elif args.command == "review":
        _print_json(
            review_run(
                args.run_id,
                {
                    "decision": args.decision,
                    "reviewer": args.reviewer,
                    "notes": args.notes,
                    "edited_draft": args.edited_draft,
                },
            )
        )
    elif args.command == "show":
        run = get_run(args.run_id)
        if run is None:
            raise LookupError(f"Run {args.run_id} wurde nicht gefunden")
        _print_json(run)
    elif args.command == "doctor":
        return _doctor(args.live)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LookupError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
