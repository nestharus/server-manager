from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.compliance import ComplianceRuleCreate, EvidenceSubmissionCreate
from app.core.context import use_audit_context
from app.repositories.db import PostgresDatabase
from app.services.authority import grant_authority
from app.services.compliance import create_rule, submit_evidence


RULES_URL = "/api/v1/compliance/rules"
EVIDENCE_URL = "/api/v1/compliance/evidence"
EVALUATIONS_URL = "/api/v1/compliance/evaluations"
ROSTER_URL = "/api/v1/roster-entries"

DEFAULT_HEADERS = {"X-Actor-Kind": "user", "X-Actor-Id": "operator"}


def audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def headers(actor_id: str, *, actor_kind: str = "user", **extra: str) -> dict[str, str]:
    return {"X-Actor-Kind": actor_kind, "X-Actor-Id": actor_id, **extra}


def grant(
    db: PostgresDatabase,
    *,
    grantee_id: str,
    permissions: frozenset[str],
    scope_kind: str = "chapter",
    scope_id: str | None = "ch-1",
) -> None:
    with use_audit_context(audit_context()):
        grant_authority(
            db,
            grantee_id=grantee_id,
            scope_kind=scope_kind,
            scope_id=scope_id,
            permissions=permissions,
            expires_at=None,
            predecessor_grant_id=None,
            actor=("user", "admin"),
        )


def grant_evaluator(db: PostgresDatabase) -> None:
    # The compliance-evaluator grant is seeded by the WU-041A migration and
    # re-seeded by the governance reset fixture, so this helper is a no-op
    # retained for call-site clarity.
    return None


def seed_chapter_and_roles(
    db: PostgresDatabase,
    *,
    chapter_id: str = "ch-1",
) -> dict[str, UUID]:
    template_id = uuid4()
    member_role_id = uuid4()
    officer_role_id = uuid4()
    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO chapter_templates (
                id,
                template_family_id,
                version,
                name,
                schema_version,
                channel_structure,
                role_structure,
                default_permission_intents
            )
            VALUES (%s, %s, 1, %s, 1, %s, %s, %s)
            """,
            (
                template_id,
                template_id,
                f"Template {chapter_id}",
                Jsonb([]),
                Jsonb(
                    [
                        {"name": "member", "ordinal": 10, "triggers_succession": False},
                        {"name": "officer", "ordinal": 20, "triggers_succession": True},
                    ]
                ),
                Jsonb([]),
            ),
        )
        conn.execute(
            """
            INSERT INTO chapters (
                id,
                name,
                template_id,
                template_snapshot,
                configuration,
                state,
                discord_resources
            )
            VALUES (%s, %s, %s, %s, %s, 'active', %s)
            """,
            (
                chapter_id,
                f"Chapter {chapter_id}",
                template_id,
                Jsonb({"role_structure": [{"name": "member"}, {"name": "officer"}]}),
                Jsonb({}),
                Jsonb({"role_ids": {"member": "discord-role-1", "officer": "discord-role-2"}}),
            ),
        )
        conn.execute(
            """
            INSERT INTO chapter_roles (
                id,
                chapter_id,
                template_id,
                name,
                ordinal,
                triggers_succession
            )
            VALUES
                (%s, %s, NULL, 'member', 10, false),
                (%s, %s, NULL, 'officer', 20, true)
            """,
            (member_role_id, chapter_id, officer_role_id, chapter_id),
        )
    return {"member": member_role_id, "officer": officer_role_id}


def create_roster_entry(
    client: TestClient,
    role_id: UUID,
    *,
    member_id: str = "member-1",
    actor_id: str = "operator",
) -> tuple[dict[str, Any], str]:
    response = client.post(
        ROSTER_URL,
        json={"chapter_id": "ch-1", "member_id": member_id, "role_id": str(role_id)},
        headers=headers(actor_id),
    )
    assert response.status_code == 201, response.text
    return response.json(), response.headers["etag"]


def create_rule_http(
    client: TestClient,
    *,
    actor_id: str = "operator",
    chapter_id: str = "ch-1",
    name: str = "Attendance",
    consequence_kind: str = "review",
    consequence_params: dict[str, Any] | None = None,
    evidence_requirements: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str]:
    response = client.post(
        RULES_URL,
        json={
            "chapter_id": chapter_id,
            "name": name,
            "cadence_kind": "weekly",
            "cadence_params": {},
            "evaluation_window_days": 7,
            "evidence_requirements": evidence_requirements
            or [{"type": "attendance", "required": True}],
            "consequence_kind": consequence_kind,
            "consequence_params": consequence_params or {},
        },
        headers=headers(actor_id),
    )
    assert response.status_code == 201, response.text
    return response.json(), response.headers["etag"]


def submit_evidence_http(
    client: TestClient,
    *,
    rule_id: str,
    actor_id: str = "operator",
    member_id: str = "member-1",
    chapter_id: str = "ch-1",
    attachment_ref: str = "s3://bucket/evidence.png",
) -> tuple[dict[str, Any], str]:
    response = client.post(
        EVIDENCE_URL,
        json={
            "rule_id": rule_id,
            "member_id": member_id,
            "chapter_id": chapter_id,
            "attachment_ref": attachment_ref,
        },
        headers=headers(actor_id),
    )
    assert response.status_code == 201, response.text
    return response.json(), response.headers["etag"]


def seed_rule(
    db: PostgresDatabase,
    *,
    actor_id: str = "operator",
    chapter_id: str = "ch-1",
    name: str = "Attendance",
    consequence_kind: str = "review",
    consequence_params: dict[str, Any] | None = None,
    evidence_requirements: list[dict[str, Any]] | None = None,
):
    with use_audit_context(audit_context()):
        read, _result = create_rule(
            db,
            ComplianceRuleCreate(
                chapter_id=chapter_id,
                name=name,
                cadence_kind="weekly",
                cadence_params={},
                evaluation_window_days=7,
                evidence_requirements=[
                    {"type": "attendance", "required": True}
                ]
                if evidence_requirements is None
                else evidence_requirements,
                consequence_kind=consequence_kind,
                consequence_params={} if consequence_params is None else consequence_params,
            ),
            actor=ActorIdentity(actor_kind="user", actor_id=actor_id),
        )
    return read


def seed_evidence(
    db: PostgresDatabase,
    *,
    rule_id: UUID,
    actor_id: str = "operator",
    member_id: str = "member-1",
    chapter_id: str = "ch-1",
    attachment_ref: str = "s3://bucket/evidence.png",
):
    with use_audit_context(audit_context()):
        read, _result = submit_evidence(
            db,
            EvidenceSubmissionCreate(
                rule_id=rule_id,
                member_id=member_id,
                chapter_id=chapter_id,
                attachment_ref=attachment_ref,
            ),
            actor=ActorIdentity(actor_kind="user", actor_id=actor_id),
        )
    return read


def fetch_one(dsn: str, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute(query, params).fetchone()
    assert row is not None
    return row


def fetch_all(dsn: str, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        return conn.execute(query, params).fetchall()


def latest_action(dsn: str, *, action_type: str) -> dict[str, Any]:
    return fetch_one(
        dsn,
        """
        SELECT *
        FROM activity_actions
        WHERE action_type = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (action_type,),
    )


def set_ocr_provider(app: FastAPI, provider: Any) -> None:
    app.state.ocr_provider = provider


class StaticOcrProvider:
    def __init__(
        self,
        *,
        raw_text: str = "attendance confirmed",
        extracted_fields: dict[str, Any] | None = None,
        confidence: str = "0.93",
    ) -> None:
        self._raw_text = raw_text
        self._extracted_fields = (
            {"attendance": True} if extracted_fields is None else extracted_fields
        )
        self._confidence = confidence

    async def extract(self, attachment_ref: str, rule_hint: str | None = None):
        from app.infrastructure.ocr import OcrExtractionResult

        return OcrExtractionResult(
            raw_text=self._raw_text,
            extracted_fields=self._extracted_fields,
            confidence=self._confidence,
        )


class FailingOcrProvider:
    def __init__(self, message: str = "ocr failed") -> None:
        self._message = message

    async def extract(self, attachment_ref: str, rule_hint: str | None = None):
        raise RuntimeError(self._message)


def iso_now() -> datetime:
    return datetime.now(tz=UTC)
