from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.applications import (
    ApplicationScope,
    FormDefinitionNotFoundError,
    FormDefinitionPublish,
    FormDefinitionRead,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.db import PostgresDatabase
from app.repositories.forms import (
    archive_current_form_for_scope,
    get_current_form_for_scope,
    insert_form,
)
from app.services.mutations import mutate_entity


FORM_PUBLISH_PAYLOAD_ALLOWLIST = {
    "name",
    "target_type",
    "scope_kind",
    "scope_id",
    "fields",
    "routing_rules",
}


def application_form_aggregate_id(scope: ApplicationScope) -> str:
    return f"application_form|{scope.scope_kind}|{scope.scope_id or ''}"


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


def _effective_routing_rules(request: FormDefinitionPublish) -> dict[str, Any]:
    rules = request.routing_rules.model_dump(mode="json")
    has_chapter_select = any(field.type == "chapter_select" for field in request.fields)
    if rules.get("review_scope") is None and not has_chapter_select:
        rules["review_scope"] = request.scope.as_persisted()
    return rules


def _row_to_read(row: dict[str, Any]) -> FormDefinitionRead:
    return FormDefinitionRead(
        id=row["id"],
        name=row["name"],
        target_type=row["target_type"],
        scope=ApplicationScope(scope_kind=row["scope_kind"], scope_id=row["scope_id"]),
        fields=row["fields"],
        routing_rules=row["routing_rules"],
        version=int(row["version"]),
        status=row["status"],
        published_at=row["published_at"],
        archived_at=row["archived_at"],
        created_at=row["created_at"],
    )


def publish_form(
    db: PostgresDatabase,
    request: FormDefinitionPublish,
    actor: ActorIdentity,
    expected_version: int,
) -> tuple[FormDefinitionRead, MutationResult]:
    validated = FormDefinitionPublish.model_validate(request)
    form_id = uuid4()
    published_at = datetime.now(UTC)
    fields = [
        field.model_dump(mode="json", exclude_unset=True)
        for field in validated.fields
    ]
    routing_rules = _effective_routing_rules(validated)
    scope = validated.scope
    next_form_version = expected_version + 1

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        archive_current_form_for_scope(
            connection,
            scope_kind=scope.scope_kind,
            scope_id=scope.scope_id,
            archived_at=published_at,
        )
        insert_form(
            connection,
            row={
                "id": form_id,
                "scope_kind": scope.scope_kind,
                "scope_id": scope.scope_id,
                "version": next_form_version,
                "name": validated.name,
                "target_type": validated.target_type.value,
                "fields": fields,
                "routing_rules": routing_rules,
                "status": "current",
                "published_by_kind": actor.actor_kind,
                "published_by_id": actor.actor_id,
                "published_at": published_at,
            },
        )
        return StateChangeDraft(
            change_type="form.published",
            payload_json={
                "form_definition_id": str(form_id),
                "name": validated.name,
                "target_type": validated.target_type.value,
                "scope_kind": scope.scope_kind,
                "scope_id": scope.scope_id,
                "version": next_form_version,
                "fields": fields,
                "routing_rules": routing_rules,
                "status": "current",
            },
            diff_json={
                "version": {"old": expected_version or None, "new": next_form_version},
                "status": {"old": None, "new": "current"},
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="application_form",
        aggregate_id=application_form_aggregate_id(scope),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface="api:/api/v1/application-forms",
        ),
        action_type="form.publish",
        action_payload={
            "name": validated.name,
            "target_type": validated.target_type.value,
            "scope_kind": scope.scope_kind,
            "scope_id": scope.scope_id,
            "fields": fields,
            "routing_rules": routing_rules,
        },
        payload_allowlist=FORM_PUBLISH_PAYLOAD_ALLOWLIST,
        mutate_projection=mutate_projection,
        scope_kind=scope.scope_kind,
        scope_id=scope.scope_id,
    )
    with db.connection() as connection:
        current = get_current_form_for_scope(
            connection,
            scope_kind=scope.scope_kind,
            scope_id=scope.scope_id,
        )
    if current is None:
        raise FormDefinitionNotFoundError(scope)
    return _row_to_read(current), result


def get_current_form(
    db: PostgresDatabase,
    *,
    scope: ApplicationScope,
) -> tuple[FormDefinitionRead, str]:
    with db.connection() as connection:
        row = get_current_form_for_scope(
            connection,
            scope_kind=scope.scope_kind,
            scope_id=scope.scope_id,
        )
    if row is None:
        raise FormDefinitionNotFoundError(scope)
    read = _row_to_read(row)
    return read, f'"{read.version}"'
