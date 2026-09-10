"""
SupportFlow SQLite store for tickets, workflow runs, and human reviews.

Tables:
  - support_tickets → imported tickets with inline customer identity

Database: data/support_tickets.db
"""

import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "support_tickets.db")
)
DB_PATH = os.getenv("SUPPORTFLOW_DB_PATH", DEFAULT_DB_PATH)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS support_tickets (
    id                  INTEGER PRIMARY KEY,
    ticket_id           TEXT NOT NULL,
    customer_name       TEXT NOT NULL,
    customer_email      TEXT NOT NULL,
    category            TEXT NOT NULL,
    category_raw        TEXT,
    subject             TEXT NOT NULL,
    description         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open',
    priority            TEXT,
    product             TEXT,
    channel             TEXT,
    resolution          TEXT,
    satisfaction_rating REAL,
    source_dataset      TEXT,
    processed_at        TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id              TEXT PRIMARY KEY,
    ticket_id           INTEGER NOT NULL,
    status              TEXT NOT NULL,
    approval_status     TEXT NOT NULL,
    state_json          TEXT,
    case_file_json      TEXT,
    error_message       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets(id)
);

CREATE TABLE IF NOT EXISTS workflow_reviews (
    run_id              TEXT PRIMARY KEY,
    decision            TEXT NOT NULL,
    reviewer            TEXT NOT NULL,
    notes               TEXT,
    edited_draft        TEXT,
    reviewed_at         TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
);
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_priority ON support_tickets(priority);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_processed ON support_tickets(processed_at);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_ticket_id ON support_tickets(ticket_id);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_source ON support_tickets(source_dataset);",
    "CREATE INDEX IF NOT EXISTS idx_runs_ticket ON workflow_runs(ticket_id);",
    "CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);",
]

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

OPEN_STATUSES = ("open", "pending")


def create_database(force: bool = False) -> bool:
    """Create the runtime database, replacing the exact DB file when forced."""
    exists = os.path.exists(DB_PATH)
    if exists and not force:
        logger.info("Database already exists: %s", DB_PATH)
        return False
    if exists:
        os.remove(DB_PATH)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    _migrate_ticket_columns(cur)
    for idx in INDEXES_SQL:
        cur.execute(idx)
    conn.commit()
    conn.close()
    logger.info("Ticket store created: %s", DB_PATH)
    return True


def _migrate_ticket_columns(cur: sqlite3.Cursor) -> None:
    existing = {row[1] for row in cur.execute("PRAGMA table_info(support_tickets)")}
    if "category_raw" not in existing:
        cur.execute("ALTER TABLE support_tickets ADD COLUMN category_raw TEXT")
    if "created_at" not in existing:
        cur.execute("ALTER TABLE support_tickets ADD COLUMN created_at TEXT")
        cur.execute(
            "UPDATE support_tickets SET created_at = COALESCE(processed_at, ?) WHERE created_at IS NULL",
            (datetime.now().isoformat(timespec="seconds"),),
        )


def ensure_db() -> bool:
    """Create the database automatically if it does not exist."""
    if not os.path.exists(DB_PATH):
        logger.warning("Database not found, creating new store at %s", DB_PATH)
        create_database(force=True)
        return True
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_ticket_columns(conn.cursor())
        for statement in INDEXES_SQL:
            conn.execute(statement)
        conn.commit()
    return False


def get_conn() -> sqlite3.Connection:
    """Open a new SQLite connection, creating the database if needed."""
    ensure_db()
    return sqlite3.connect(DB_PATH)


class db_connection:
    """Context manager for database connections."""

    def __enter__(self):
        ensure_db()
        self.conn = sqlite3.connect(DB_PATH)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


def _ticket_row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "ticket_id": row[1],
        "customer_name": row[2],
        "customer_email": row[3],
        "category": row[4],
        "category_raw": row[5],
        "subject": row[6],
        "description": row[7],
        "status": row[8],
        "priority": row[9],
        "product": row[10],
        "channel": row[11],
        "resolution": row[12],
        "satisfaction_rating": row[13],
        "source_dataset": row[14],
        "processed_at": row[15],
        "created_at": row[16],
    }


TICKET_SELECT_SQL = """
    SELECT
        id, ticket_id, customer_name, customer_email, category, category_raw, subject,
        description, status, priority, product, channel, resolution,
        satisfaction_rating, source_dataset, processed_at, created_at
    FROM support_tickets
"""


def query_open_tickets(limit: int = 30) -> list[dict]:
    """Return unprocessed open/pending tickets ordered by priority."""
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                {TICKET_SELECT_SQL}
                WHERE status IN (?, ?)
                  AND processed_at IS NULL
                ORDER BY
                    CASE LOWER(COALESCE(priority, 'low'))
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        ELSE 3
                    END,
                    datetime(created_at) ASC,
                    id ASC
                LIMIT ?
                """,
                (*OPEN_STATUSES, limit),
            )
            rows = cur.fetchall()
        return [_ticket_row_to_dict(r) for r in rows]
    except sqlite3.DatabaseError as exc:
        logger.error("Database error in query_open_tickets: %s", exc)
        return []


def query_ticket_by_id(ticket_id: int) -> dict | None:
    """Return one ticket by internal database id."""
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"{TICKET_SELECT_SQL} WHERE id = ?", (ticket_id,))
            row = cur.fetchone()
        return _ticket_row_to_dict(row) if row else None
    except sqlite3.DatabaseError as exc:
        logger.error("Database error in query_ticket_by_id(%s): %s", ticket_id, exc)
        return None


def clear_imported_tickets(source_dataset: str) -> int:
    """Remove previously imported tickets for a dataset."""
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM support_tickets WHERE source_dataset = ?",
            (source_dataset,),
        )
        deleted = cur.rowcount
        conn.commit()
    return deleted


def bulk_insert_tickets(tickets: list[dict]) -> int:
    """Insert many tickets in a single transaction."""
    if not tickets:
        return 0

    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM support_tickets")
        next_id = cur.fetchone()[0] + 1

        rows = []
        for offset, ticket in enumerate(tickets):
            rows.append((
                next_id + offset,
                ticket["ticket_id"],
                ticket["customer_name"],
                ticket["customer_email"],
                ticket["category"],
                ticket.get("category_raw"),
                ticket["subject"],
                ticket["description"],
                ticket["status"],
                ticket.get("priority"),
                ticket.get("product"),
                ticket.get("channel"),
                ticket.get("resolution"),
                ticket.get("satisfaction_rating"),
                ticket.get("source_dataset"),
                ticket.get("processed_at"),
                ticket.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            ))

        cur.executemany(
            """
            INSERT INTO support_tickets (
                id, ticket_id, customer_name, customer_email, category, category_raw, subject,
                description, status, priority, product, channel, resolution,
                satisfaction_rating, source_dataset, processed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def mark_ticket_processed(ticket_id: int) -> None:
    """Mark a ticket as processed without changing its CSV-derived status."""
    with db_connection() as conn:
        cursor = conn.execute(
            "UPDATE support_tickets SET processed_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), ticket_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Ticket {ticket_id} was not found during finalization")
        conn.commit()
    logger.info("Ticket #%s marked as processed", ticket_id)


def count_tickets(source_dataset: str | None = None) -> int:
    """Count tickets, optionally filtered by source dataset."""
    with db_connection() as conn:
        if source_dataset:
            row = conn.execute(
                "SELECT COUNT(*) FROM support_tickets WHERE source_dataset = ?",
                (source_dataset,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()
    return row[0]


def create_workflow_run(run_id: str, ticket_id: int) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO workflow_runs (
                run_id, ticket_id, status, approval_status, created_at, updated_at
            ) VALUES (?, ?, 'running', 'pending', ?, ?)
            """,
            (run_id, ticket_id, now, now),
        )
        conn.commit()


def update_workflow_run(
    run_id: str,
    *,
    status: str,
    approval_status: str,
    state: dict | None = None,
    case_file: dict | None = None,
    error_message: str | None = None,
) -> None:
    with db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, approval_status = ?, state_json = ?, case_file_json = ?,
                error_message = ?, updated_at = ?
            WHERE run_id = ?
            """,
            (
                status,
                approval_status,
                json.dumps(state, ensure_ascii=False) if state is not None else None,
                json.dumps(case_file, ensure_ascii=False) if case_file is not None else None,
                error_message,
                datetime.now().isoformat(timespec="seconds"),
                run_id,
            ),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Workflow run {run_id} was not found")
        conn.commit()


def _run_row_to_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["state"] = json.loads(result.pop("state_json")) if result.get("state_json") else None
    result["case_file"] = (
        json.loads(result.pop("case_file_json")) if result.get("case_file_json") else None
    )
    return result


def get_workflow_run(run_id: str) -> dict | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
    return _run_row_to_dict(row) if row else None


def find_existing_ticket_run(ticket_id: int) -> dict | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM workflow_runs WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
    return _run_row_to_dict(row) if row else None


def list_workflow_runs(status: str | None = None) -> list[dict]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM workflow_runs WHERE status = ? ORDER BY created_at ASC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM workflow_runs ORDER BY created_at ASC").fetchall()
    return [_run_row_to_dict(row) for row in rows]


def save_workflow_review(
    run_id: str,
    *,
    decision: str,
    reviewer: str,
    notes: str | None,
    edited_draft: str | None,
) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO workflow_reviews (
                run_id, decision, reviewer, notes, edited_draft, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                decision,
                reviewer,
                notes,
                edited_draft,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def get_workflow_review(run_id: str) -> dict | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM workflow_reviews WHERE run_id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    from src.tools.logger import setup_logging

    setup_logging()

    force = "--force" in sys.argv
    create_database(force=force)
