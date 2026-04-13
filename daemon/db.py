"""SQLite database helpers for the Humility daemon."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_DATABASE_PATH = Path("discord.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chapters (
    slug TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    officer_role_id INTEGER NOT NULL,
    member_role_id INTEGER NOT NULL,
    applicant_role_id INTEGER NOT NULL,
    applications_channel_id INTEGER NOT NULL,
    tickets_channel_id INTEGER NOT NULL,
    incidents_channel_id INTEGER NOT NULL,
    form_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id TEXT NOT NULL,
    chapter_slug TEXT NOT NULL,
    applicant_id INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    queue_message_id INTEGER,
    queue_channel_id INTEGER,
    thread_id INTEGER,
    claimer_id INTEGER,
    decided_by INTEGER,
    decided_at TEXT,
    decision_reason TEXT,
    answers_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_type TEXT NOT NULL,
    chapter_slug TEXT,
    requester_id INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    status TEXT NOT NULL,
    queue_message_id INTEGER,
    queue_channel_id INTEGER,
    thread_id INTEGER,
    claimer_id INTEGER,
    closed_at TEXT,
    closed_by INTEGER,
    subject TEXT,
    initial_description TEXT
);

CREATE TABLE IF NOT EXISTS chapter_blacklist (
    chapter_slug TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    added_by INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (chapter_slug, user_id)
);
"""


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path


def resolve_database_config(env: Mapping[str, str] | None = None) -> DatabaseConfig:
    source = env if env is not None else {}
    raw_path = source.get("DATABASE_PATH")
    if raw_path:
        return DatabaseConfig(path=Path(raw_path))
    return DatabaseConfig(path=DEFAULT_DATABASE_PATH)


def connect_database(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def bootstrap_database(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def open_database(path: str | Path) -> sqlite3.Connection:
    conn = connect_database(path)
    bootstrap_database(conn)
    return conn


def close_database(conn: sqlite3.Connection) -> None:
    conn.close()


def insert_chapter(
    conn: sqlite3.Connection,
    *,
    slug: str,
    display_name: str,
    category_id: int,
    officer_role_id: int,
    member_role_id: int,
    applicant_role_id: int,
    applications_channel_id: int,
    tickets_channel_id: int,
    incidents_channel_id: int,
    form_path: str,
    created_at: str,
    archived_at: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO chapters (
            slug,
            display_name,
            category_id,
            officer_role_id,
            member_role_id,
            applicant_role_id,
            applications_channel_id,
            tickets_channel_id,
            incidents_channel_id,
            form_path,
            created_at,
            archived_at
        ) VALUES (
            :slug,
            :display_name,
            :category_id,
            :officer_role_id,
            :member_role_id,
            :applicant_role_id,
            :applications_channel_id,
            :tickets_channel_id,
            :incidents_channel_id,
            :form_path,
            :created_at,
            :archived_at
        )
        """,
        {
            "slug": slug,
            "display_name": display_name,
            "category_id": category_id,
            "officer_role_id": officer_role_id,
            "member_role_id": member_role_id,
            "applicant_role_id": applicant_role_id,
            "applications_channel_id": applications_channel_id,
            "tickets_channel_id": tickets_channel_id,
            "incidents_channel_id": incidents_channel_id,
            "form_path": form_path,
            "created_at": created_at,
            "archived_at": archived_at,
        },
    )


def get_chapter_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM chapters WHERE slug = ?", (slug,)).fetchone()


def create_submission(
    conn: sqlite3.Connection,
    *,
    form_id: str,
    chapter_slug: str,
    applicant_id: int,
    submitted_at: str,
    status: str,
    queue_message_id: int | None,
    queue_channel_id: int | None,
    thread_id: int | None,
    claimer_id: int | None,
    decided_by: int | None,
    decided_at: str | None,
    decision_reason: str | None,
    answers_json: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO submissions (
            form_id,
            chapter_slug,
            applicant_id,
            submitted_at,
            status,
            queue_message_id,
            queue_channel_id,
            thread_id,
            claimer_id,
            decided_by,
            decided_at,
            decision_reason,
            answers_json
        ) VALUES (
            :form_id,
            :chapter_slug,
            :applicant_id,
            :submitted_at,
            :status,
            :queue_message_id,
            :queue_channel_id,
            :thread_id,
            :claimer_id,
            :decided_by,
            :decided_at,
            :decision_reason,
            :answers_json
        )
        """,
        {
            "form_id": form_id,
            "chapter_slug": chapter_slug,
            "applicant_id": applicant_id,
            "submitted_at": submitted_at,
            "status": status,
            "queue_message_id": queue_message_id,
            "queue_channel_id": queue_channel_id,
            "thread_id": thread_id,
            "claimer_id": claimer_id,
            "decided_by": decided_by,
            "decided_at": decided_at,
            "decision_reason": decision_reason,
            "answers_json": answers_json,
        },
    )
    return int(cursor.lastrowid)


def get_submission_by_id(conn: sqlite3.Connection, submission_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()


def update_submission_refs(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    queue_message_id: int | None,
    queue_channel_id: int | None,
    thread_id: int | None,
) -> None:
    conn.execute(
        """
        UPDATE submissions
        SET queue_message_id = ?,
            queue_channel_id = ?,
            thread_id = ?
        WHERE id = ?
        """,
        (queue_message_id, queue_channel_id, thread_id, submission_id),
    )


def transition_submission_status(
    conn: sqlite3.Connection,
    submission_id: int,
    from_status: str | tuple[str, ...] | list[str],
    to_status: str,
    **kwargs: int | str | None,
) -> bool:
    allowed_columns = {
        "queue_message_id",
        "queue_channel_id",
        "thread_id",
        "claimer_id",
        "decided_by",
        "decided_at",
        "decision_reason",
    }
    unexpected_columns = set(kwargs) - allowed_columns
    if unexpected_columns:
        names = ", ".join(sorted(unexpected_columns))
        raise ValueError(f"Unsupported submission transition columns: {names}")

    from_statuses = (from_status,) if isinstance(from_status, str) else tuple(from_status)
    if not from_statuses:
        raise ValueError("from_status must include at least one status.")

    assignments = ["status = ?"]
    params: list[int | str | None] = [to_status]
    for column, value in kwargs.items():
        assignments.append(f"{column} = ?")
        params.append(value)

    status_placeholders = ", ".join("?" for _ in from_statuses)
    params.extend([submission_id, *from_statuses])
    cursor = conn.execute(
        f"""
        UPDATE submissions
        SET {", ".join(assignments)}
        WHERE id = ?
          AND status IN ({status_placeholders})
        """,
        params,
    )
    return cursor.rowcount == 1


def load_active_submission_ids(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        """
        SELECT id
        FROM submissions
        WHERE status IN ('pending', 'claimed', 'interview')
        ORDER BY id
        """
    ).fetchall()
    return [int(row["id"]) for row in rows]


def has_active_submission(conn: sqlite3.Connection, applicant_id: int, chapter_slug: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM submissions
        WHERE applicant_id = ?
          AND chapter_slug = ?
          AND status IN ('pending', 'claimed', 'interview')
        LIMIT 1
        """,
        (applicant_id, chapter_slug),
    ).fetchone()
    return row is not None


def create_ticket(
    conn: sqlite3.Connection,
    *,
    ticket_type: str,
    chapter_slug: str | None,
    requester_id: int,
    opened_at: str,
    status: str,
    queue_message_id: int | None,
    queue_channel_id: int | None,
    thread_id: int | None,
    claimer_id: int | None,
    closed_at: str | None,
    closed_by: int | None,
    subject: str | None,
    initial_description: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO tickets (
            ticket_type,
            chapter_slug,
            requester_id,
            opened_at,
            status,
            queue_message_id,
            queue_channel_id,
            thread_id,
            claimer_id,
            closed_at,
            closed_by,
            subject,
            initial_description
        ) VALUES (
            :ticket_type,
            :chapter_slug,
            :requester_id,
            :opened_at,
            :status,
            :queue_message_id,
            :queue_channel_id,
            :thread_id,
            :claimer_id,
            :closed_at,
            :closed_by,
            :subject,
            :initial_description
        )
        """,
        {
            "ticket_type": ticket_type,
            "chapter_slug": chapter_slug,
            "requester_id": requester_id,
            "opened_at": opened_at,
            "status": status,
            "queue_message_id": queue_message_id,
            "queue_channel_id": queue_channel_id,
            "thread_id": thread_id,
            "claimer_id": claimer_id,
            "closed_at": closed_at,
            "closed_by": closed_by,
            "subject": subject,
            "initial_description": initial_description,
        },
    )


def get_ticket_by_id(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def add_blacklist_entry(
    conn: sqlite3.Connection,
    *,
    chapter_slug: str,
    user_id: int,
    reason: str | None,
    added_by: int,
    added_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO chapter_blacklist (
            chapter_slug,
            user_id,
            reason,
            added_by,
            added_at
        ) VALUES (
            :chapter_slug,
            :user_id,
            :reason,
            :added_by,
            :added_at
        )
        """,
        {
            "chapter_slug": chapter_slug,
            "user_id": user_id,
            "reason": reason,
            "added_by": added_by,
            "added_at": added_at,
        },
    )


def get_blacklist_entry(
    conn: sqlite3.Connection,
    chapter_slug: str,
    user_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM chapter_blacklist WHERE chapter_slug = ? AND user_id = ?",
        (chapter_slug, user_id),
    ).fetchone()
