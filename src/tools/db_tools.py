"""
Enterprise Multi-Agent System — Ticket Store
=============================================
SQLite runtime store for imported support tickets and processing state.

Tables:
  - support_tickets → imported tickets with inline customer identity

Database: data/support_tickets.db
"""

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "support_tickets.db")
DB_PATH = os.path.abspath(DB_PATH)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS support_tickets (
    id                  INTEGER PRIMARY KEY,
    ticket_id           TEXT NOT NULL,
    customer_name       TEXT NOT NULL,
    customer_email      TEXT NOT NULL,
    category            TEXT NOT NULL,
    subject             TEXT NOT NULL,
    description         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open',
    priority            TEXT,
    product             TEXT,
    channel             TEXT,
    resolution          TEXT,
    satisfaction_rating REAL,
    source_dataset      TEXT,
    processed_at        TEXT
);
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_priority ON support_tickets(priority);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_processed ON support_tickets(processed_at);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_ticket_id ON support_tickets(ticket_id);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_source ON support_tickets(source_dataset);",
]

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

OPEN_STATUSES = ("open", "pending")


def create_database(force: bool = False) -> bool:
    """Create an empty runtime database with the support_tickets schema."""
    exists = os.path.exists(DB_PATH)
    if exists and not force:
        logger.info("Database already exists: %s", DB_PATH)
        return False

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    for idx in INDEXES_SQL:
        cur.execute(idx)
    conn.commit()
    conn.close()
    logger.info("Ticket store created: %s", DB_PATH)
    return True


def ensure_db() -> bool:
    """Create the database automatically if it does not exist."""
    if not os.path.exists(DB_PATH):
        logger.warning("Database not found, creating new store at %s", DB_PATH)
        create_database(force=True)
        return True
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
        "subject": row[5],
        "description": row[6],
        "status": row[7],
        "priority": row[8],
        "product": row[9],
        "channel": row[10],
        "resolution": row[11],
        "satisfaction_rating": row[12],
        "source_dataset": row[13],
        "processed_at": row[14],
    }


TICKET_SELECT_SQL = """
    SELECT
        id, ticket_id, customer_name, customer_email, category, subject,
        description, status, priority, product, channel, resolution,
        satisfaction_rating, source_dataset, processed_at
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
                    id
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
            ))

        cur.executemany(
            """
            INSERT INTO support_tickets (
                id, ticket_id, customer_name, customer_email, category, subject,
                description, status, priority, product, channel, resolution,
                satisfaction_rating, source_dataset, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def mark_ticket_processed(ticket_id: int) -> None:
    """Mark a ticket as processed without changing its CSV-derived status."""
    try:
        with db_connection() as conn:
            conn.execute(
                "UPDATE support_tickets SET processed_at = ? WHERE id = ?",
                (datetime.now().isoformat(timespec="seconds"), ticket_id),
            )
            conn.commit()
        logger.info("Ticket #%s marked as processed", ticket_id)
    except sqlite3.DatabaseError as exc:
        logger.error("Database error in mark_ticket_processed(%s): %s", ticket_id, exc)


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


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    from src.tools.logger import setup_logging

    setup_logging()

    force = "--force" in sys.argv
    create_database(force=force)
