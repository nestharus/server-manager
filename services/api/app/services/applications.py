from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import TypeAdapter
from psycopg import Connection, errors
from psycopg.rows import dict_row

from app.contracts.actor import ActorIdentity
from app.contracts.audit import AuditContextRead, CorrelationHeadersRead
from app.contracts.applications import (
    APPLICATION_REASSIGN_ACTION_TYPE,
    APPLICATION_REASSIGN_CHANGE_TYPE,
    APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST,
    ApplicationAlreadyClaimedError,
    ApplicationDecisionReasonRequiredError,
    ApplicationFormField,
    ApplicationInterviewRequest,
    ApplicationInterviewThreadMismatchError,
    ApplicationListForbiddenError,
    ApplicationListRead,
    ApplicationNotFoundError,
    ApplicationNotOwnerError,
    ApplicationRead,
    ApplicationReactivateOwnerRequiredError,
    ApplicationReactivateRequest,
    ApplicationReviewNotesRequiredError,
    ApplicationSubmission,
    ApplicationTransitionRequest,
    ApplicationWaitlistReasonRequiredError,
    ApplicationWaitlistRequest,
    DuplicateApplicationCreateError,
    FormDefinitionNotFoundError,
    InvalidApplicationResponseError,
    InvalidApplicationTransitionError,
    PublicApplicationSubmission,
)
from app.contracts.authority import AuthorityRequirement
from app.contracts.mutations import MutationRequest, MutationResult, StaleMutationError, StateChangeDraft
from app.core.context import get_current_audit_context, use_audit_context
from app.repositories.applications import (
    get_application,
    get_application_by_client_application_id,
    get_application_for_update,
    insert_application,
    insert_review_row,
    list_applications as list_application_rows,
    update_application,
)
from app.repositories.db import PostgresDatabase
from app.repositories.forms import get_current_form_for_scope
from app.repositories.members import fetch_member_by_id
from app.repositories.public_chapters import fetch_active_public_chapter
from app.services.authority import current_time, evaluate, list_grants_for_grantee
from app.services.members import (
    is_synthetic_member,
    resolve_or_create_real_discord_member,
)
from app.services.mutations import mutate_entity
from app.services.notifications import (
    NotificationEmitError,
    emit_application_public_submitted_event,
)


logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    ("submitted", "route"): "queued",
    ("submitted", "reassign"): "submitted",
    ("queued", "reassign"): "queued",
    ("queued", "claim"): "claimed",
    ("claimed", "reassign"): "claimed",
    ("claimed", "review"): "in_review",
    ("in_review", "reassign"): "in_review",
    ("in_review", "request_interview"): "interview",
    ("in_review", "waitlist"): "waitlisted",
    ("interview", "reassign"): "interview",
    ("interview", "waitlist"): "waitlisted",
    ("interview", "approve"): "approved",
    ("interview", "deny"): "denied",
    ("in_review", "approve"): "approved",
    ("in_review", "deny"): "denied",
    ("waitlisted", "reassign"): "waitlisted",
    ("waitlisted", "reactivate"): "claimed",
    ("submitted", "withdraw"): "withdrawn",
    ("queued", "withdraw"): "withdrawn",
    ("claimed", "withdraw"): "withdrawn",
    ("in_review", "withdraw"): "withdrawn",
    ("interview", "withdraw"): "withdrawn",
    ("waitlisted", "withdraw"): "withdrawn",
}

AUDIT_ACTION_TYPE = {
    "route": "application.route",
    "claim": "application.claim",
    "review": "application.review",
    "request_interview": "application.interview",
    "waitlist": "application.waitlist",
    "reassign": APPLICATION_REASSIGN_ACTION_TYPE,
    "reactivate": "application.reactivate",
    "approve": "application.decision",
    "deny": "application.decision",
    "withdraw": "application.review",
}

AUDIT_CHANGE_TYPE = {
    "route": "application.queued",
    "claim": "application.transitioned",
    "review": "application.transitioned",
    "request_interview": "application.transitioned",
    "waitlist": "application.transitioned",
    "reassign": APPLICATION_REASSIGN_CHANGE_TYPE,
    "reactivate": "application.transitioned",
    "approve": "application.transitioned",
    "deny": "application.transitioned",
    "withdraw": "application.transitioned",
}

TRANSITION_PAYLOAD_ALLOWLIST = {
    "route": {"action"},
    "claim": {"action", "reviewer_id"},
    "review": {"action", "reviewer_id", "notes"},
    "request_interview": {
        "action",
        "reviewer_id",
        "thread_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
    "waitlist": {
        "action",
        "reviewer_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
    "reassign": set(APPLICATION_REASSIGN_PAYLOAD_ALLOWLIST),
    "reactivate": {
        "action",
        "reviewer_id",
        "new_owner_id",
        "reason",
        "originating_actor_kind",
        "originating_actor_id",
    },
    "approve": {"action", "reviewer_id", "decision_reason"},
    "deny": {"action", "reviewer_id", "decision_reason"},
    "withdraw": {"action", "reviewer_id", "notes"},
}

APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST = {
    "applicant_id",
    "form_definition_id",
    "form_version",
    "target_scope_kind",
    "target_scope_id",
    "responses",
    "client_application_id",
}

APPLICATION_READ_PERMISSIONS = (
    "application.claim",
    "application.review",
    "application.request_interview",
    "application.waitlist",
    "application.reactivate",
    "application.approve",
    "application.deny",
    "application.withdraw",
)

AUTHENTICATED_SUBMIT_SURFACE = "api:/api/v1/applications"
PUBLIC_SUBMIT_SURFACE = "api:/api/v1/public/applications"
_APPLICATION_FORM_FIELD_ADAPTER = TypeAdapter(ApplicationFormField)


class _SubmitApplicationResult(tuple[ApplicationRead, MutationResult]):
    def __new__(
        cls,
        read: ApplicationRead,
        result: MutationResult,
    ) -> "_SubmitApplicationResult":
        return super().__new__(cls, (read, result))

    @property
    def read(self) -> ApplicationRead:
        return self[0]

    @property
    def result(self) -> MutationResult:
        return self[1]

    def __await__(self):
        async def _read() -> ApplicationRead:
            return self.read

        return _read().__await__()


def _generated_audit_context() -> AuditContextRead:
    correlation_id = uuid4()
    return AuditContextRead(
        correlation_id=correlation_id,
        causation_id=None,
        headers=CorrelationHeadersRead(
            x_correlation_id=correlation_id,
            x_causation_id=None,
        ),
    )


def application_aggregate_id(application_id: UUID) -> str:
    return str(application_id)


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=None,
        request_surface=request_surface,
    )


def _row_to_read(row: dict[str, Any]) -> ApplicationRead:
    return ApplicationRead(
        id=row["id"],
        applicant_id=row["applicant_id"],
        form_definition_id=row["form_definition_id"],
        form_version=int(row["form_version"]),
        form_snapshot=row["form_snapshot"],
        target_scope={
            "scope_kind": row["target_scope_kind"],
            "scope_id": row["target_scope_id"],
        },
        responses=row["responses"],
        state=row["state"],
        owner_id=row["owner_id"],
        interview_thread_id=row.get("interview_thread_id"),
        decision_reason=row["decision_reason"],
        submitted_at=row["submitted_at"],
        queued_at=row["queued_at"],
        claimed_at=row["claimed_at"],
        review_started_at=row["review_started_at"],
        decided_at=row["decided_at"],
        withdrawn_at=row["withdrawn_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _fetch_application_row(
    connection: Connection[Any],
    application_id: UUID,
) -> dict[str, Any]:
    row = get_application(connection, application_id=application_id)
    if row is None:
        raise ApplicationNotFoundError(application_id)
    return row


def _reviewer_id(actor: ActorIdentity, action: str) -> UUID | None:
    if action == "route":
        return None
    if action == "withdraw" and actor.actor_kind != "user":
        return None
    if actor.actor_kind != "user":
        raise ValueError("review actions require a user actor")
    return UUID(actor.actor_id)


def _originating_actor(
    request: ApplicationTransitionRequest,
    actor: ActorIdentity,
) -> tuple[str | None, str | None]:
    if actor.actor_kind == "service":
        return request.originating_actor_kind, request.originating_actor_id
    return actor.actor_kind, actor.actor_id


def _require_authority(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    permission: str,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    decision = evaluate(
        requirement=AuthorityRequirement(
            scope_kind=scope_kind,  # type: ignore[arg-type]
            scope_id=scope_id,
            permission=permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise PermissionError("authority requirement denied")


def _require_submit_authority(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    applicant_id: UUID,
    scope_kind: str,
    scope_id: str | None,
) -> None:
    if actor.actor_kind == "user" and actor.actor_id == str(applicant_id):
        return
    _require_authority(
        db,
        actor=actor,
        permission="application.submit",
        scope_kind=scope_kind,
        scope_id=scope_id,
    )


def _raise_synthetic_application_error(*, code: str, message: str) -> None:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={"code": code, "message": message},
    )


def _require_non_synthetic_application_member(
    connection: Connection[Any],
    member_id: UUID,
    *,
    code: str,
    message: str,
) -> dict[str, Any]:
    member = fetch_member_by_id(connection, member_id)
    if member is None:
        raise ValueError(f"member {member_id} was not found")
    if is_synthetic_member(member):
        _raise_synthetic_application_error(code=code, message=message)
    return member


def require_transition_authority(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    action: str,
    target_scope: dict[str, Any],
) -> None:
    permission = "application.review" if action == "reassign" else f"application.{action}"
    _require_authority(
        db,
        actor=actor,
        permission=permission,
        scope_kind=str(target_scope["scope_kind"]),
        scope_id=target_scope.get("scope_id"),
    )


def require_application_read_authority(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    application: ApplicationRead,
) -> None:
    # D8 interprets application read as: applicant identity OR any of the
    # transition permissions (claim/review/approve/deny/withdraw) at
    # form_snapshot.target_scope. No dedicated application.read permission.
    if actor.actor_kind == "user" and actor.actor_id == str(application.applicant_id):
        return
    target_scope = application.form_snapshot["target_scope"]
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    for permission in APPLICATION_READ_PERMISSIONS:
        decision = evaluate(
            requirement=AuthorityRequirement(
                scope_kind=str(target_scope["scope_kind"]),  # type: ignore[arg-type]
                scope_id=target_scope.get("scope_id"),
                permission=permission,
            ),
            grants=grants,
            at=current_time(),
        )
        if decision.allowed:
            return
    raise PermissionError("authority requirement denied")


def _has_application_list_authority(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    scope_kind: str,
    scope_id: str | None,
) -> bool:
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    candidate_scopes = [(scope_kind, scope_id)]
    if scope_kind != "global":
        candidate_scopes.append(("global", None))
    for candidate_scope_kind, candidate_scope_id in candidate_scopes:
        for permission in APPLICATION_READ_PERMISSIONS:
            decision = evaluate(
                requirement=AuthorityRequirement(
                    scope_kind=candidate_scope_kind,  # type: ignore[arg-type]
                    scope_id=candidate_scope_id,
                    permission=permission,
                ),
                grants=grants,
                at=current_time(),
            )
            if decision.allowed:
                return True
    return False


def list_applications(
    db: PostgresDatabase,
    *,
    actor: ActorIdentity,
    states: frozenset[str] | None = None,
    scope_kind: str | None = None,
    scope_id: str | None = None,
    owner_id: UUID | None = None,
    limit: int = 50,
    after_id: UUID | None = None,
) -> ApplicationListRead:
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if scope_kind == "chapter" and scope_id is None:
        raise ValueError("scope_id is required when scope_kind is chapter")
    if scope_kind == "global" and scope_id is not None:
        raise ValueError("scope_id must be omitted when scope_kind is global")

    auth_scope_kind = scope_kind or "global"
    auth_scope_id = scope_id if scope_kind is not None else None
    if not _has_application_list_authority(
        db,
        actor=actor,
        scope_kind=auth_scope_kind,
        scope_id=auth_scope_id,
    ):
        raise ApplicationListForbiddenError()

    with db.connection() as connection:
        rows = list_application_rows(
            connection,
            states=states,
            scope_kind=scope_kind,
            scope_id=scope_id,
            owner_id=owner_id,
            limit=limit,
            after_id=after_id,
        )
    page_rows = rows[:limit]
    next_after_id = page_rows[-1]["id"] if len(rows) > limit and page_rows else None
    return ApplicationListRead(
        items=[_row_to_read(row) for row in page_rows],
        next_after_id=next_after_id,
    )


def build_form_snapshot(form_row: dict[str, Any]) -> dict[str, Any]:
    routing_rules = dict(form_row["routing_rules"])
    target_scope = routing_rules.get("review_scope") or {
        "scope_kind": form_row["scope_kind"],
        "scope_id": form_row["scope_id"],
    }
    return {
        "schema_version": 1,
        "form_definition_id": str(form_row["id"]),
        "name": form_row["name"],
        "target_type": form_row["target_type"],
        "scope_kind": form_row["scope_kind"],
        "scope_id": form_row["scope_id"],
        "form_version": int(form_row["version"]),
        "target_scope": target_scope,
        "fields": form_row["fields"],
        "routing_rules": routing_rules,
    }


def validate_application_responses(
    fields: list[dict[str, Any]],
    responses: dict[str, Any],
    *,
    connection: Connection[Any] | None = None,
    submitted_scope: dict[str, Any] | None = None,
) -> None:
    field_map = {
        field.id: field
        for field in (
            _APPLICATION_FORM_FIELD_ADAPTER.validate_python(raw) for raw in fields
        )
    }
    response_keys = set(responses)
    unknown = response_keys - set(field_map)
    if unknown:
        raise InvalidApplicationResponseError(
            f"unknown response fields: {', '.join(sorted(unknown))}"
        )
    missing = sorted(
        field_id
        for field_id, field in field_map.items()
        if field.required and field_id not in responses
    )
    if missing:
        raise InvalidApplicationResponseError(
            f"missing required response fields: {', '.join(missing)}"
        )

    for field_id, value in responses.items():
        field = field_map[field_id]
        if field.type in {"short", "long"}:
            if not isinstance(value, str):
                raise InvalidApplicationResponseError(f"{field_id} must be a string")
            if field.required and not value.strip():
                raise InvalidApplicationResponseError(f"{field_id} is required")
            if field.max_length is not None and len(value) > field.max_length:
                raise InvalidApplicationResponseError(f"{field_id} exceeds max_length")
        elif field.type == "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise InvalidApplicationResponseError(f"{field_id} must be a number")
        elif field.type == "select":
            if not isinstance(value, str) or value not in (field.options or []):
                raise InvalidApplicationResponseError(f"{field_id} must be a configured option")
        elif field.type == "multi_select":
            if not isinstance(value, list):
                raise InvalidApplicationResponseError(f"{field_id} must be a list")
            if field.required and not value:
                raise InvalidApplicationResponseError(f"{field_id} is required")
            for item in value:
                if not isinstance(item, str):
                    raise InvalidApplicationResponseError(
                        f"{field_id} entries must be strings"
                    )
            if len(value) != len(set(value)):
                raise InvalidApplicationResponseError(f"{field_id} must not contain duplicates")
            options = set(field.options or [])
            if any(item not in options for item in value):
                raise InvalidApplicationResponseError(f"{field_id} must contain configured options")
        elif field.type == "boolean" and not isinstance(value, bool):
            raise InvalidApplicationResponseError(f"{field_id} must be a boolean")
        elif field.type == "chapter_select":
            if not isinstance(value, str):
                raise InvalidApplicationResponseError(f"{field_id} must be a chapter id")
            chapter_id = value.strip()
            if not chapter_id:
                raise InvalidApplicationResponseError(f"{field_id} is required")
            if (
                submitted_scope is not None
                and submitted_scope.get("scope_kind") == "chapter"
                and chapter_id != submitted_scope.get("scope_id")
            ):
                raise InvalidApplicationResponseError(
                    f"{field_id} must match submitted chapter scope"
                )
            if connection is not None and fetch_active_public_chapter(connection, chapter_id) is None:
                raise InvalidApplicationResponseError(f"{field_id} must be an active chapter")


def _chapter_select_field_ids(form_row: dict[str, Any]) -> list[str]:
    field_ids: list[str] = []
    for raw in form_row["fields"]:
        field = _APPLICATION_FORM_FIELD_ADAPTER.validate_python(raw)
        if field.type == "chapter_select" and field.required:
            field_ids.append(field.id)
    return field_ids


def _chapter_selector_override(
    connection: Connection[Any],
    *,
    submitted_scope: dict[str, Any],
    responses: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str | None] | None]:
    current_global = _get_current_form_for_submit(
        connection,
        scope_kind="global",
        scope_id=None,
    )
    if current_global is None:
        return None, None
    chapter_field_ids = _chapter_select_field_ids(current_global)
    if len(chapter_field_ids) != 1:
        return None, None

    chapter_field_id = chapter_field_ids[0]
    if submitted_scope["scope_kind"] == "global":
        raise InvalidApplicationResponseError(
            "chapter_select forms require a submitted chapter scope"
        )
    if submitted_scope["scope_kind"] != "chapter":
        # Future non-chapter scope types use their own current-form lookup path.
        return None, None

    selected_chapter_id = submitted_scope.get("scope_id")
    response_chapter_id = responses.get(chapter_field_id)
    if not isinstance(response_chapter_id, str) or response_chapter_id.strip() != selected_chapter_id:
        raise InvalidApplicationResponseError(
            "chapter_select response must match submitted chapter scope"
        )
    return current_global, {
        "scope_kind": "chapter",
        "scope_id": selected_chapter_id,
    }


def _get_current_form_for_submit(
    connection: Connection[Any],
    *,
    scope_kind: str,
    scope_id: str | None,
) -> dict[str, Any] | None:
    form_row = get_current_form_for_scope(
        connection,
        scope_kind=scope_kind,
        scope_id=scope_id,
    )
    if form_row is not None:
        return form_row
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            """
            SELECT id,
                   scope_kind,
                   scope_id,
                   version,
                   name,
                   target_type,
                   fields,
                   routing_rules,
                   status,
                   published_by_kind,
                   published_by_id,
                   published_at,
                   archived_at,
                   created_at
            FROM form_definitions
            WHERE scope_kind = %s
              AND scope_id IS NOT DISTINCT FROM %s
              AND status = 'current'
            ORDER BY version DESC
            LIMIT 1
            """,
            (scope_kind, scope_id),
        ).fetchone()


def validate_required_transition_fields(
    action: str,
    request: ApplicationTransitionRequest,
) -> None:
    if action == "reassign" and request.new_owner_id is None:
        raise ValueError("new_owner_id is required for reassign")
    if action in {"approve", "deny"}:
        reason = None if request.decision_reason is None else request.decision_reason.strip()
        if not reason:
            raise ApplicationDecisionReasonRequiredError(action)
    if action == "review":
        notes = None if request.notes is None else request.notes.strip()
        if not notes:
            raise ApplicationReviewNotesRequiredError()
    if action == "waitlist":
        reason = _transition_reason(request)
        if not reason:
            raise ApplicationWaitlistReasonRequiredError()


def validate_transition(
    current_state: str,
    action: str,
    request: ApplicationTransitionRequest,
    *,
    application_id: UUID | None = None,
) -> str:
    validate_required_transition_fields(action, request)
    next_state = VALID_TRANSITIONS.get((current_state, action))
    if next_state is None:
        raise InvalidApplicationTransitionError(
            application_id=application_id,
            from_state=current_state,
            action=action,
        )
    return next_state


def _transition_diff(
    current: dict[str, Any],
    updated: dict[str, Any],
    *,
    notes: str | None,
) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    diff: dict[str, Any] = {
        "state": {"old": current["state"], "new": updated["state"]},
    }
    for key in (
        "owner_id",
        "interview_thread_id",
        "decision_reason",
        "queued_at",
        "claimed_at",
        "review_started_at",
        "decided_at",
        "withdrawn_at",
    ):
        if current.get(key) != updated.get(key):
            old = current.get(key)
            new = updated.get(key)
            diff[key] = {
                "old": normalize(old),
                "new": normalize(new),
            }
    if notes is not None:
        diff["notes"] = {"old": None, "new": notes}
    return diff


def _transition_reason(request: ApplicationTransitionRequest) -> str | None:
    raw = request.reason if request.reason is not None else request.notes
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _submit_application_internal(
    db: PostgresDatabase,
    request: ApplicationSubmission,
    actor: ActorIdentity,
    *,
    request_surface: str,
) -> _SubmitApplicationResult:
    if get_current_audit_context() is None:
        with use_audit_context(_generated_audit_context()):
            return _submit_application_internal(
                db,
                request,
                actor,
                request_surface=request_surface,
            )

    validated = ApplicationSubmission.model_validate(request)
    application_id = uuid4()
    submitted_at = datetime.now(UTC)

    with db.transaction() as connection:
        applicant = fetch_member_by_id(connection, validated.applicant_id)
        if applicant is None:
            raise ValueError(f"member {validated.applicant_id} was not found")
        if is_synthetic_member(applicant):
            _raise_synthetic_application_error(
                code="applicant_synthetic_not_allowed",
                message=(
                    "Synthetic public-intake members cannot submit applications."
                ),
            )

        submitted_scope = validated.scope.as_persisted()
        form_row, target_scope_override = _chapter_selector_override(
            connection,
            submitted_scope=submitted_scope,
            responses=validated.responses,
        )
        if form_row is None:
            form_row = _get_current_form_for_submit(
                connection,
                scope_kind=validated.scope.scope_kind,
                scope_id=validated.scope.scope_id,
            )
        if form_row is None:
            raise FormDefinitionNotFoundError(validated.scope)

        if validated.client_application_id is not None:
            existing = get_application_by_client_application_id(
                connection,
                applicant_id=validated.applicant_id,
                client_application_id=validated.client_application_id,
            )
            if existing is not None:
                raise DuplicateApplicationCreateError(_row_to_read(existing))

        _require_submit_authority(
            db,
            actor=actor,
            applicant_id=validated.applicant_id,
            scope_kind=form_row["scope_kind"],
            scope_id=form_row["scope_id"],
        )

        snapshot = build_form_snapshot(form_row)
        if target_scope_override is not None:
            snapshot["target_scope"] = target_scope_override
        validate_application_responses(
            snapshot["fields"],
            validated.responses,
            connection=connection,
            submitted_scope=submitted_scope,
        )
        target_scope = snapshot["target_scope"]
        persisted = {
            "id": application_id,
            "applicant_id": validated.applicant_id,
            "form_definition_id": form_row["id"],
            "form_version": int(form_row["version"]),
            "form_snapshot": snapshot,
            "target_scope_kind": target_scope["scope_kind"],
            "target_scope_id": target_scope.get("scope_id"),
            "responses": validated.responses,
            "state": "submitted",
            "owner_id": None,
            "interview_thread_id": None,
            "decision_reason": None,
            "client_application_id": validated.client_application_id,
            "submitted_at": submitted_at,
            "queued_at": None,
            "claimed_at": None,
            "review_started_at": None,
            "decided_at": None,
            "withdrawn_at": None,
        }

        def submit_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            insert_application(active_connection, row=persisted)
            return StateChangeDraft(
                change_type="application.submitted",
                payload_json={
                    "application_id": str(application_id),
                    "applicant_id": str(validated.applicant_id),
                    "form_definition_id": str(form_row["id"]),
                    "form_version": int(form_row["version"]),
                    "form_snapshot": snapshot,
                    "target_scope_kind": target_scope["scope_kind"],
                    "target_scope_id": target_scope.get("scope_id"),
                    "responses": validated.responses,
                    "client_application_id": validated.client_application_id,
                    "state": "submitted",
                },
            )

        action_payload = {
            "applicant_id": str(validated.applicant_id),
            "form_definition_id": str(form_row["id"]),
            "form_version": int(form_row["version"]),
            "target_scope_kind": target_scope["scope_kind"],
            "target_scope_id": target_scope.get("scope_id"),
            "responses": validated.responses,
            "client_application_id": validated.client_application_id,
        }
        try:
            mutate_entity(
                db=db,
                connection=connection,
                aggregate_type="application",
                aggregate_id=application_aggregate_id(application_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface=request_surface,
                ),
                action_type="application.submit",
                action_payload=action_payload,
                payload_allowlist=APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST,
                mutate_projection=submit_projection,
                scope_kind=target_scope["scope_kind"],
                scope_id=target_scope.get("scope_id"),
            )
        except errors.UniqueViolation as error:
            if validated.client_application_id is None:
                raise
            with db.connection() as recovery_connection:
                existing = get_application_by_client_application_id(
                    recovery_connection,
                    applicant_id=validated.applicant_id,
                    client_application_id=validated.client_application_id,
                )
            if existing is None:
                raise
            raise DuplicateApplicationCreateError(_row_to_read(existing)) from error

        route_request = ApplicationTransitionRequest(action="route")
        result = _transition_application_locked(
            db=db,
            connection=connection,
            application_id=application_id,
            expected_version=1,
            request=route_request,
            actor=actor,
            action_payload=action_payload,
            payload_allowlist=APPLICATION_SUBMIT_PAYLOAD_ALLOWLIST,
            request_surface=request_surface,
        )
        read = _row_to_read(_fetch_application_row(connection, application_id))
    return _SubmitApplicationResult(read, result)


def submit_application(
    db: PostgresDatabase,
    request: ApplicationSubmission,
    actor: ActorIdentity,
) -> _SubmitApplicationResult:
    return _submit_application_internal(
        db,
        request,
        actor,
        request_surface=AUTHENTICATED_SUBMIT_SURFACE,
    )


async def submit_public_application_with_receipt(
    db: PostgresDatabase,
    public_submission: PublicApplicationSubmission,
    *,
    discord_user_id: str,
) -> UUID:
    if get_current_audit_context() is None:
        with use_audit_context(_generated_audit_context()):
            return await submit_public_application_with_receipt(
                db,
                public_submission,
                discord_user_id=discord_user_id,
            )

    validated = PublicApplicationSubmission.model_validate(public_submission)
    client_application_id = (
        str(uuid4())
        if validated.client_application_id is None
        else validated.client_application_id
    )
    member = await resolve_or_create_real_discord_member(
        db,
        discord_user_id=discord_user_id,
    )
    internal_submission = ApplicationSubmission(
        applicant_id=member.id,
        scope=validated.scope,
        responses=validated.responses,
        client_application_id=client_application_id,
    )
    actor = ActorIdentity(actor_kind="user", actor_id=str(member.id))
    try:
        created = _submit_application_internal(
            db,
            internal_submission,
            actor,
            request_surface=PUBLIC_SUBMIT_SURFACE,
        )
    except DuplicateApplicationCreateError as error:
        return error.application.id
    try:
        emit_application_public_submitted_event(
            db,
            application=created.read,
            discord_user_id=discord_user_id,
        )
    except (NotificationEmitError, RuntimeError):
        logger.exception(
            "notification emit failed for application %s; submit row remains durably committed",
            created.read.id,
        )
    return created.read.id


def read_application(
    db: PostgresDatabase,
    *,
    application_id: UUID,
) -> tuple[ApplicationRead, str]:
    with db.connection() as connection:
        read = _row_to_read(_fetch_application_row(connection, application_id))
    return read, f'"{read.version}"'


def _transition_application_locked(
    *,
    db: PostgresDatabase,
    connection: Connection[Any] | None,
    application_id: UUID,
    expected_version: int,
    request: ApplicationTransitionRequest,
    actor: ActorIdentity,
    action_payload: dict[str, Any],
    payload_allowlist: set[str],
    request_surface: str,
) -> MutationResult:
    action = request.action.value if hasattr(request.action, "value") else str(request.action)
    review_id = uuid4()

    def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
        current = get_application_for_update(
            active_connection,
            application_id=application_id,
        )
        if current is None:
            raise ApplicationNotFoundError(application_id)
        next_state = validate_transition(
            str(current["state"]),
            action,
            request,
            application_id=application_id,
        )
        now = datetime.now(UTC)
        reviewer_id = _reviewer_id(actor, action)
        if (
            action in {"review", "approve", "deny", "request_interview", "waitlist"}
            and current["owner_id"] != reviewer_id
        ):
            raise ApplicationNotOwnerError(
                current_owner_id=current["owner_id"],
                actor_id=reviewer_id,
            )
        notes = None if request.notes is None else request.notes.strip()
        reason = _transition_reason(request)
        if action in {"request_interview", "waitlist", "reactivate"}:
            notes = reason
        decision_reason = (
            None if request.decision_reason is None else request.decision_reason.strip()
        )
        updated = dict(current)
        updated["state"] = next_state
        if action == "route":
            updated["queued_at"] = now
        elif action == "claim":
            if reviewer_id is not None:
                _require_non_synthetic_application_member(
                    active_connection,
                    reviewer_id,
                    code="owner_synthetic_not_allowed",
                    message="Synthetic public-intake members cannot own applications.",
                )
            updated["owner_id"] = reviewer_id
            updated["claimed_at"] = now
        elif action == "review":
            updated["review_started_at"] = now
        elif action == "request_interview":
            updated["interview_thread_id"] = (
                request.thread_id
                if request.thread_id is not None
                else current.get("interview_thread_id")
            )
        elif action == "waitlist":
            pass
        elif action == "reassign":
            if request.new_owner_id is None:
                raise ValueError("new_owner_id is required for reassign")
            _require_non_synthetic_application_member(
                active_connection,
                request.new_owner_id,
                code="owner_synthetic_not_allowed",
                message="Synthetic public-intake members cannot own applications.",
            )
            updated["owner_id"] = request.new_owner_id
        elif action == "reactivate":
            next_owner_id = request.new_owner_id or current["owner_id"]
            if next_owner_id is None:
                raise ApplicationReactivateOwnerRequiredError()
            _require_non_synthetic_application_member(
                active_connection,
                next_owner_id,
                code="owner_synthetic_not_allowed",
                message="Synthetic public-intake members cannot own applications.",
            )
            updated["owner_id"] = next_owner_id
            updated["claimed_at"] = now
        elif action in {"approve", "deny"}:
            updated["decision_reason"] = decision_reason
            updated["decided_at"] = now
        elif action == "withdraw":
            updated["withdrawn_at"] = now

        update_application(
            active_connection,
            application_id=application_id,
            row=updated,
        )
        aggregate_seq = expected_version + 1
        review_action = "review" if action == "reassign" else action
        insert_review_row(
            active_connection,
            row={
                "id": review_id,
                "application_id": application_id,
                "aggregate_seq": aggregate_seq,
                "reviewer_id": reviewer_id,
                "actor_kind": actor.actor_kind,
                "actor_id": actor.actor_id,
                "action": review_action,
                "from_state": current["state"],
                "to_state": next_state,
                "notes": notes,
                "decision_reason": decision_reason,
            },
        )
        payload_json = {
            "application_id": str(application_id),
            "application_review_id": str(review_id),
            "action": action,
            "from_state": current["state"],
            "to_state": next_state,
            "reviewer_id": None if reviewer_id is None else str(reviewer_id),
            "notes": notes,
            "decision_reason": decision_reason,
        }
        if action == "request_interview":
            payload_json["thread_id"] = request.thread_id
        if action in {"reassign", "reactivate"} and request.new_owner_id is not None:
            payload_json["new_owner_id"] = str(request.new_owner_id)
        if action in {"request_interview", "waitlist", "reactivate"} and reason is not None:
            payload_json["reason"] = reason

        return StateChangeDraft(
            change_type=AUDIT_CHANGE_TYPE[action],
            payload_json=payload_json,
            diff_json=_transition_diff(current, updated, notes=notes),
        )

    return mutate_entity(
        db=db,
        connection=connection,
        aggregate_type="application",
        aggregate_id=application_aggregate_id(application_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=request_surface,
        ),
        action_type=AUDIT_ACTION_TYPE[action],
        action_payload=action_payload,
        payload_allowlist=payload_allowlist,
        mutate_projection=mutate_projection,
        scope_kind=None,
        scope_id=None,
    )


def transition_application(
    db: PostgresDatabase,
    application_id: UUID,
    expected_version: int,
    request: ApplicationTransitionRequest,
    actor: ActorIdentity,
    request_surface: str | None = None,
    skip_authority_check: bool = False,
    allow_route_transition: bool = False,
) -> tuple[ApplicationRead, MutationResult]:
    action = request.action.value
    if action == "route" and not allow_route_transition:
        raise InvalidApplicationTransitionError(
            application_id=application_id,
            from_state="public",
            action=action,
        )
    with db.connection() as read_connection:
        current = _fetch_application_row(read_connection, application_id)
    target_scope = current["form_snapshot"]["target_scope"]
    if not skip_authority_check:
        require_transition_authority(
            db,
            actor=actor,
            action=action,
            target_scope=target_scope,
        )
    reviewer_id = _reviewer_id(actor, action)
    if (
        action in {"request_interview", "waitlist"}
        and current["owner_id"] != reviewer_id
    ):
        raise ApplicationNotOwnerError(
            current_owner_id=current["owner_id"],
            actor_id=reviewer_id,
        )
    if action == "request_interview":
        idempotent = _maybe_idempotent_interview(
            current=current,
            application_id=application_id,
            expected_version=expected_version,
            request=request,
        )
        if idempotent is not None:
            return _row_to_read(idempotent), MutationResult(
                version=int(idempotent["version"]),
                etag=f'"{int(idempotent["version"])}"',
            )
    originating_actor_kind, originating_actor_id = _originating_actor(request, actor)
    action_payload = {
        "action": action,
        "reviewer_id": None if reviewer_id is None else str(reviewer_id),
        "notes": request.notes,
        "decision_reason": request.decision_reason,
        "thread_id": request.thread_id,
        "reason": request.reason,
        "new_owner_id": None if request.new_owner_id is None else str(request.new_owner_id),
        "originating_actor_kind": originating_actor_kind,
        "originating_actor_id": originating_actor_id,
    }
    try:
        result = _transition_application_locked(
            db=db,
            connection=None,
            application_id=application_id,
            expected_version=expected_version,
            request=request,
            actor=actor,
            action_payload=action_payload,
            payload_allowlist=TRANSITION_PAYLOAD_ALLOWLIST[action],
            request_surface=request_surface
            or f"api:/api/v1/applications/{application_id}/transitions",
        )
    except StaleMutationError as error:
        if action != "claim":
            raise
        with db.connection() as recovery_connection:
            live = _fetch_application_row(recovery_connection, application_id)
        if live["state"] != "queued" or live["owner_id"] is not None:
            raise ApplicationAlreadyClaimedError(application=_row_to_read(live)) from error
        raise

    with db.connection() as read_connection:
        read = _row_to_read(_fetch_application_row(read_connection, application_id))
    return read, result


def _maybe_idempotent_interview(
    *,
    current: dict[str, Any],
    application_id: UUID,
    expected_version: int,
    request: ApplicationTransitionRequest,
) -> dict[str, Any] | None:
    stored_thread_id = current.get("interview_thread_id")
    requested_thread_id = request.thread_id
    if stored_thread_id and requested_thread_id and stored_thread_id != requested_thread_id:
        raise ApplicationInterviewThreadMismatchError(
            current_thread_id=str(stored_thread_id),
            requested_thread_id=requested_thread_id,
        )
    if current["state"] != "interview" or not stored_thread_id:
        return None
    if requested_thread_id is not None and requested_thread_id != stored_thread_id:
        return None
    if int(current["version"]) != expected_version:
        raise StaleMutationError(
            aggregate_type="application",
            aggregate_id=application_aggregate_id(application_id),
            expected_version=expected_version,
            current_version=int(current["version"]),
        )
    return current


def request_interview(
    db: PostgresDatabase,
    *,
    application_id: UUID,
    expected_version: int,
    request: ApplicationInterviewRequest,
    actor: ActorIdentity,
) -> tuple[ApplicationRead, str]:
    transition_request = ApplicationTransitionRequest(
        action="request_interview",
        thread_id=request.thread_id,
        reason=request.reason,
        originating_actor_kind=request.originating_actor_kind,
        originating_actor_id=request.originating_actor_id,
    )
    read, result = transition_application(
        db,
        application_id=application_id,
        expected_version=expected_version,
        request=transition_request,
        actor=actor,
        request_surface=f"api:/api/v1/applications/{application_id}/interview",
    )
    return read, result.etag


def waitlist_application(
    db: PostgresDatabase,
    *,
    application_id: UUID,
    expected_version: int,
    request: ApplicationWaitlistRequest,
    actor: ActorIdentity,
) -> tuple[ApplicationRead, str]:
    transition_request = ApplicationTransitionRequest(
        action="waitlist",
        reason=request.reason,
        originating_actor_kind=request.originating_actor_kind,
        originating_actor_id=request.originating_actor_id,
    )
    read, result = transition_application(
        db,
        application_id=application_id,
        expected_version=expected_version,
        request=transition_request,
        actor=actor,
        request_surface=f"api:/api/v1/applications/{application_id}/waitlist",
    )
    return read, result.etag


def reactivate_application(
    db: PostgresDatabase,
    *,
    application_id: UUID,
    expected_version: int,
    request: ApplicationReactivateRequest,
    actor: ActorIdentity,
) -> tuple[ApplicationRead, str]:
    transition_request = ApplicationTransitionRequest(
        action="reactivate",
        new_owner_id=request.new_owner_id,
        reason=request.reason,
        originating_actor_kind=request.originating_actor_kind,
        originating_actor_id=request.originating_actor_id,
    )
    read, result = transition_application(
        db,
        application_id=application_id,
        expected_version=expected_version,
        request=transition_request,
        actor=actor,
        request_surface=f"api:/api/v1/applications/{application_id}/reactivate",
    )
    return read, result.etag
