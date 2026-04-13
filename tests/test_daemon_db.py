import importlib
import sqlite3

import pytest


CHAPTER_ROW = {
    "slug": "dark-nemesis",
    "display_name": "Dark Nemesis",
    "category_id": 101,
    "officer_role_id": 102,
    "member_role_id": 103,
    "applicant_role_id": 104,
    "applications_channel_id": 105,
    "tickets_channel_id": 106,
    "incidents_channel_id": 107,
    "form_path": "forms/dark-nemesis.yaml",
    "created_at": "2026-04-13T00:00:00Z",
    "archived_at": None,
}

SUBMISSION_ROW = {
    "form_id": "dark-nemesis",
    "chapter_slug": "dark-nemesis",
    "applicant_id": 201,
    "submitted_at": "2026-04-13T00:01:00Z",
    "status": "pending",
    "queue_message_id": 301,
    "queue_channel_id": 302,
    "thread_id": 303,
    "claimer_id": None,
    "decided_by": None,
    "decided_at": None,
    "decision_reason": None,
    "answers_json": '{"in_game_name":"nest","hours_per_day":"4"}',
}

TICKET_ROW = {
    "ticket_type": "chapter_support",
    "chapter_slug": "dark-nemesis",
    "requester_id": 401,
    "opened_at": "2026-04-13T00:02:00Z",
    "status": "open",
    "queue_message_id": 501,
    "queue_channel_id": 502,
    "thread_id": 503,
    "claimer_id": None,
    "closed_at": None,
    "closed_by": None,
    "subject": "Need help",
    "initial_description": "Application queue question.",
}

BLACKLIST_ROW = {
    "chapter_slug": "dark-nemesis",
    "user_id": 601,
    "reason": "Prior harassment",
    "added_by": 602,
    "added_at": "2026-04-13T00:03:00Z",
}

EXPECTED_SCHEMAS = {
    "chapters": [
        ("slug", "TEXT", 0, None, 1),
        ("display_name", "TEXT", 1, None, 0),
        ("category_id", "INTEGER", 1, None, 0),
        ("officer_role_id", "INTEGER", 1, None, 0),
        ("member_role_id", "INTEGER", 1, None, 0),
        ("applicant_role_id", "INTEGER", 1, None, 0),
        ("applications_channel_id", "INTEGER", 1, None, 0),
        ("tickets_channel_id", "INTEGER", 1, None, 0),
        ("incidents_channel_id", "INTEGER", 1, None, 0),
        ("form_path", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
        ("archived_at", "TEXT", 0, None, 0),
    ],
    "submissions": [
        ("id", "INTEGER", 0, None, 1),
        ("form_id", "TEXT", 1, None, 0),
        ("chapter_slug", "TEXT", 1, None, 0),
        ("applicant_id", "INTEGER", 1, None, 0),
        ("submitted_at", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("queue_message_id", "INTEGER", 0, None, 0),
        ("queue_channel_id", "INTEGER", 0, None, 0),
        ("thread_id", "INTEGER", 0, None, 0),
        ("claimer_id", "INTEGER", 0, None, 0),
        ("decided_by", "INTEGER", 0, None, 0),
        ("decided_at", "TEXT", 0, None, 0),
        ("decision_reason", "TEXT", 0, None, 0),
        ("answers_json", "TEXT", 1, None, 0),
    ],
    "tickets": [
        ("id", "INTEGER", 0, None, 1),
        ("ticket_type", "TEXT", 1, None, 0),
        ("chapter_slug", "TEXT", 0, None, 0),
        ("requester_id", "INTEGER", 1, None, 0),
        ("opened_at", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("queue_message_id", "INTEGER", 0, None, 0),
        ("queue_channel_id", "INTEGER", 0, None, 0),
        ("thread_id", "INTEGER", 0, None, 0),
        ("claimer_id", "INTEGER", 0, None, 0),
        ("closed_at", "TEXT", 0, None, 0),
        ("closed_by", "INTEGER", 0, None, 0),
        ("subject", "TEXT", 0, None, 0),
        ("initial_description", "TEXT", 0, None, 0),
    ],
    "chapter_blacklist": [
        ("chapter_slug", "TEXT", 1, None, 1),
        ("user_id", "INTEGER", 1, None, 2),
        ("reason", "TEXT", 0, None, 0),
        ("added_by", "INTEGER", 1, None, 0),
        ("added_at", "TEXT", 1, None, 0),
    ],
}


def import_db_module():
    try:
        return importlib.import_module("daemon.db")
    except Exception as exc:  # pragma: no cover - import failures should fail loudly
        pytest.fail(f"Could not import daemon.db: {exc!r}")


@pytest.fixture
def db_module():
    return import_db_module()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "daemon.db"


@pytest.fixture
def conn(db_module, db_path):
    connection = db_module.open_database(db_path)
    yield connection
    try:
        db_module.close_database(connection)
    except sqlite3.ProgrammingError:
        pass


def table_info(conn: sqlite3.Connection, table_name: str) -> list[tuple[str, str, int, str | None, int]]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [
        (row["name"], row["type"], row["notnull"], row["dflt_value"], row["pk"])
        for row in rows
    ]


def test_public_api_matches_contract(db_module):
    for name in (
        "open_database",
        "close_database",
        "insert_chapter",
        "get_chapter_by_slug",
        "create_submission",
        "get_submission_by_id",
        "create_ticket",
        "get_ticket_by_id",
        "add_blacklist_entry",
        "get_blacklist_entry",
    ):
        assert hasattr(db_module, name)


@pytest.mark.parametrize("path_factory", [lambda path: path, lambda path: str(path)])
def test_open_database_accepts_str_or_path_and_bootstraps_database(db_module, tmp_path, path_factory):
    db_path = tmp_path / "daemon.db"
    conn = db_module.open_database(path_factory(db_path))

    try:
        assert isinstance(conn, sqlite3.Connection)
        assert db_path.exists()
        assert conn.row_factory is sqlite3.Row

        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert isinstance(journal_mode, str)
        assert journal_mode.lower() == "wal"

        user_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert user_tables == set(EXPECTED_SCHEMAS)
    finally:
        db_module.close_database(conn)


def test_open_database_creates_documented_table_schemas(conn):
    for table_name, expected_schema in EXPECTED_SCHEMAS.items():
        assert table_info(conn, table_name) == expected_schema


def test_close_database_closes_connection(db_module, db_path):
    conn = db_module.open_database(db_path)

    db_module.close_database(conn)

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_insert_and_get_chapter_round_trip_returns_sqlite_row(db_module, conn):
    db_module.insert_chapter(conn, **CHAPTER_ROW)

    row = db_module.get_chapter_by_slug(conn, CHAPTER_ROW["slug"])

    assert isinstance(row, sqlite3.Row)
    assert dict(row) == CHAPTER_ROW


def test_get_chapter_by_slug_rejects_sql_injection_input(db_module, conn):
    db_module.insert_chapter(conn, **CHAPTER_ROW)

    row = db_module.get_chapter_by_slug(conn, "missing' OR 1=1 --")

    assert row is None
    assert conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0] == 1


def test_create_and_get_submission_round_trip(db_module, conn):
    db_module.create_submission(conn, **SUBMISSION_ROW)
    submission_id = conn.execute("SELECT id FROM submissions").fetchone()["id"]

    row = db_module.get_submission_by_id(conn, submission_id)

    assert isinstance(row, sqlite3.Row)
    assert row["id"] == submission_id
    for key, value in SUBMISSION_ROW.items():
        assert row[key] == value


def test_create_and_get_ticket_round_trip(db_module, conn):
    db_module.create_ticket(conn, **TICKET_ROW)
    ticket_id = conn.execute("SELECT id FROM tickets").fetchone()["id"]

    row = db_module.get_ticket_by_id(conn, ticket_id)

    assert isinstance(row, sqlite3.Row)
    assert row["id"] == ticket_id
    for key, value in TICKET_ROW.items():
        assert row[key] == value


def test_add_and_get_blacklist_entry_round_trip(db_module, conn):
    db_module.add_blacklist_entry(conn, **BLACKLIST_ROW)

    row = db_module.get_blacklist_entry(conn, BLACKLIST_ROW["chapter_slug"], BLACKLIST_ROW["user_id"])

    assert isinstance(row, sqlite3.Row)
    assert dict(row) == BLACKLIST_ROW
