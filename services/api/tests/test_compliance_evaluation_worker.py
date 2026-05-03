from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import psycopg
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.repositories.db import PostgresDatabase
from app.services.compliance import compliance_evaluator_actor
from app.tasks.compliance import compliance_evaluation_worker_tick

from .compliance_helpers import (
    create_roster_entry,
    fetch_all,
    fetch_one,
    grant,
    grant_evaluator,
    latest_action,
    seed_chapter_and_roles,
    seed_evidence,
    seed_rule,
)


pytestmark = pytest.mark.usefixtures("governance_dsn")


def _seed_member_rule(
    client: TestClient,
    app: FastAPI,
    *,
    member_id: str = "member-1",
    consequence_kind: str = "review",
    consequence_params: dict | None = None,
    evidence_requirements: list[dict] | None = None,
) -> dict:
    db: PostgresDatabase = app.state.container.core.db()
    roles = seed_chapter_and_roles(db)
    grant(db, grantee_id="operator", permissions=frozenset({"roster.write", "roster.read", "roster.remove"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_rule.write"}))
    grant(db, grantee_id="operator", permissions=frozenset({"compliance_evidence.submit"}))
    create_roster_entry(client, roles["member"], member_id=member_id)
    rule = seed_rule(
        app,
        consequence_kind=consequence_kind,
        consequence_params={} if consequence_params is None else consequence_params,
        evidence_requirements=evidence_requirements,
    )
    grant_evaluator(db)
    return {"rule": rule, "roles": roles}


def _mark_evidence_completed(
    db: PostgresDatabase,
    *,
    evidence_id,
    extracted_fields: dict,
    extracted_fields_corrected: dict | None = None,
) -> None:
    has_overlay = extracted_fields_corrected is not None
    with db.connection() as connection:
        connection.execute(
            """
            UPDATE evidence_submissions
            SET raw_text = %s,
                extracted_fields = %s,
                extracted_fields_corrected = %s,
                extraction_status = %s,
                extraction_confidence = 0.95,
                submitted_at = %s,
                extraction_error = NULL,
                corrected_by_member_id = %s,
                corrected_at = %s,
                correction_reason = %s
            WHERE id = %s
            """,
            (
                "ocr text",
                Jsonb(extracted_fields),
                Jsonb(extracted_fields_corrected) if has_overlay else None,
                "corrected" if has_overlay else "completed",
                datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
                "operator" if has_overlay else None,
                datetime(2026, 4, 19, 12, 0, tzinfo=UTC) if has_overlay else None,
                "verified manually" if has_overlay else None,
                evidence_id,
            ),
        )


def test_worker_inserts_one_evaluation_for_member_rule_period(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: a worker tick inserts at most one evaluation for a member/rule/period tuple."""
    _seed_member_rule(client, app)

    result = compliance_evaluation_worker_tick(app.state.container.core.db(), now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    rows = fetch_all(governance_dsn, "SELECT * FROM compliance_evaluations", ())

    assert result is not None
    assert len(result) == 1
    assert len(rows) == 1


def test_worker_is_idempotent_on_repeat_tick(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: rerunning the worker for the same period does not create duplicate evaluations."""
    _seed_member_rule(client, app)

    first = compliance_evaluation_worker_tick(app.state.container.core.db(), now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    second = compliance_evaluation_worker_tick(app.state.container.core.db(), now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    rows = fetch_all(governance_dsn, "SELECT * FROM compliance_evaluations", ())

    assert first is not None
    assert second == []
    assert len(rows) == 1


def test_worker_routes_under_review_through_roster_service(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: an auto-applied violation routes the consequence through roster transition audit instead of raw SQL."""
    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(
        client,
        app,
        consequence_kind="under_review",
        consequence_params={"auto_apply": True},
    )
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(db, evidence_id=evidence.id, extracted_fields={"attendance": False})

    result = compliance_evaluation_worker_tick(db, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    roster = fetch_one(governance_dsn, "SELECT status FROM roster_entries WHERE member_id = %s", ("member-1",))
    transition = latest_action(governance_dsn, action_type="roster_entry.transition")

    assert result is not None
    assert result[0].consequence_applied == "under_review_applied"
    assert roster["status"] == "under_review"
    assert transition["actor_id"] == "compliance-evaluator"


def test_worker_records_review_queue_for_review_consequence(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: a violation under review-only policy records review_queued without mutating roster state."""
    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(client, app, consequence_kind="review")
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(db, evidence_id=evidence.id, extracted_fields={"attendance": False})

    result = compliance_evaluation_worker_tick(db, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))

    assert result is not None
    assert result[0].result == "violation"
    assert result[0].consequence_applied == "review_queued"
    assert result[0].review_status == "pending"


def test_worker_records_insufficient_evidence_without_consequence(
    client: TestClient,
    app: FastAPI,
) -> None:
    """AC4: when no evidence exists, the worker records insufficient_evidence and no roster consequence."""
    _seed_member_rule(client, app, consequence_kind="under_review", consequence_params={"auto_apply": True})

    result = compliance_evaluation_worker_tick(app.state.container.core.db(), now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))

    assert result is not None
    assert result[0].result == "insufficient_evidence"
    assert result[0].consequence_applied == "none"


def test_worker_installs_root_audit_context(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: the worker creates audit rows under the compliance-evaluator service actor even without ambient context."""
    _seed_member_rule(client, app)

    compliance_evaluation_worker_tick(app.state.container.core.db(), now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    action = latest_action(governance_dsn, action_type="compliance_evaluation.create")

    assert action["actor_kind"] == "service"
    assert action["actor_id"] == "compliance-evaluator"
    assert action["correlation_id"] is not None


def test_worker_evaluates_evidence_in_shared_transaction(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Evidence read and evaluation insert must run on the same connection (same tx)."""
    from app.repositories.compliance import ComplianceRepository

    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(
        client,
        app,
        consequence_kind="under_review",
        consequence_params={"auto_apply": True},
    )
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(db, evidence_id=evidence.id, extracted_fields={"attendance": False})

    observed: dict[str, object] = {}
    original_list = ComplianceRepository._list_evidence_for_rule_period_on
    original_insert = ComplianceRepository._insert_evaluation_if_absent_on

    def tracking_list(self, connection, **kwargs):
        observed["read"] = connection
        return original_list(self, connection, **kwargs)

    def tracking_insert(self, connection, **kwargs):
        observed["insert"] = connection
        return original_insert(self, connection, **kwargs)

    monkeypatch.setattr(
        ComplianceRepository,
        "_list_evidence_for_rule_period_on",
        tracking_list,
    )
    monkeypatch.setattr(
        ComplianceRepository,
        "_insert_evaluation_if_absent_on",
        tracking_insert,
    )

    result = compliance_evaluation_worker_tick(db, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))

    assert result is not None
    assert len(result) == 1
    assert isinstance(observed["read"], psycopg.Connection)
    assert observed["read"] is observed["insert"]


def test_worker_reloads_roster_status_in_tx(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: roster status is re-read inside the per-member tx so a concurrent transition suppresses auto-apply."""
    from app.repositories.compliance import ComplianceRepository

    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(
        client,
        app,
        consequence_kind="under_review",
        consequence_params={"auto_apply": True},
    )
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(db, evidence_id=evidence.id, extracted_fields={"attendance": False})

    original_list = ComplianceRepository._list_current_roster_members_by_chapter_on

    def mutating_list(self, connection, **kwargs):
        rows = original_list(self, connection, **kwargs)
        with db.connection() as mutation_connection:
            mutation_connection.execute(
                "UPDATE roster_entries SET status = 'under_review', updated_at = NOW() WHERE member_id = %s",
                ("member-1",),
            )
        return rows

    monkeypatch.setattr(
        ComplianceRepository,
        "_list_current_roster_members_by_chapter_on",
        mutating_list,
    )

    result = compliance_evaluation_worker_tick(db, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))
    roster = fetch_one(governance_dsn, "SELECT status FROM roster_entries WHERE member_id = %s", ("member-1",))

    assert result is not None
    assert len(result) == 1
    assert result[0].consequence_applied == "none"
    assert result[0].review_status == "not_required"
    assert roster["status"] == "under_review"


def test_correction_merges_with_ocr_fields(
    client: TestClient,
    app: FastAPI,
) -> None:
    """Corrected fields overlay OCR output — untouched requirement types remain visible during evaluation."""
    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(
        client,
        app,
        consequence_kind="review",
        evidence_requirements=[
            {"type": "attendance", "required": True},
            {"type": "receipt", "required": True},
        ],
    )
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(
        db,
        evidence_id=evidence.id,
        extracted_fields={"attendance": False, "receipt": True},
        extracted_fields_corrected={"attendance": True},
    )

    result = compliance_evaluation_worker_tick(db, now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC))

    assert result is not None
    assert len(result) == 1
    assert result[0].result == "compliant"


def test_manual_run_preserves_operator_attribution_on_roster_transition(
    client: TestClient,
    app: FastAPI,
    governance_dsn: str,
) -> None:
    """AC4: manual /evaluations/run uses the service actor for writes while recording the operator as the originating actor."""
    db: PostgresDatabase = app.state.container.core.db()
    seeded = _seed_member_rule(
        client,
        app,
        consequence_kind="under_review",
        consequence_params={"auto_apply": True},
    )
    evidence = seed_evidence(app, rule_id=seeded["rule"].id)
    _mark_evidence_completed(db, evidence_id=evidence.id, extracted_fields={"attendance": False})
    grant(
        db,
        grantee_id="operator",
        scope_kind="global",
        scope_id=None,
        permissions=frozenset({"compliance_evaluation.write"}),
    )

    service = app.state.container.services.compliance()
    result = service.run_scheduled_compliance_evaluations(
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
        actor=compliance_evaluator_actor(),
        originating_actor=ActorIdentity(actor_kind="user", actor_id="operator"),
        source="manual_trigger",
    )
    transition = latest_action(governance_dsn, action_type="roster_entry.transition")

    assert result is not None
    assert transition["actor_id"] == "compliance-evaluator"
    assert transition["request_json"]["originating_actor_id"] == "operator"
