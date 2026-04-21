from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.notifications import (
    NotificationRuleCreate,
    NotificationRuleListRead,
    NotificationRuleNotFoundError,
    NotificationRulePatch,
    NotificationRuleRead,
)
from app.repositories.db import PostgresDatabase
from app.repositories.notifications import (
    fetch_notification_rule,
    fetch_notification_rule_for_update,
    insert_notification_rule,
    list_notification_rules as list_notification_rule_rows,
    update_notification_rule,
)
from app.services.mutations import mutate_entity

RULE_PAYLOAD_FIELDS = {
    "trigger_json",
    "scope_kind",
    "scope_id",
    "recipients_json",
    "channel",
    "template_json",
    "actionable",
    "grouping",
    "enabled",
}


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


def _rule_from_row(row: dict[str, Any]) -> NotificationRuleRead:
    return NotificationRuleRead(
        id=row["id"],
        trigger_json=row["trigger_json"],
        scope_kind=row["scope_kind"],
        scope_id=row["scope_id"],
        recipients_json=row["recipients_json"],
        channel=row["channel"],
        template_json=row["template_json"],
        actionable=row["actionable"],
        grouping=row["grouping"],
        enabled=row["enabled"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
    )


def _fetch_rule_row(connection: Connection[Any], rule_id: UUID) -> dict[str, Any]:
    row = fetch_notification_rule(connection, rule_id)
    if row is None:
        raise NotificationRuleNotFoundError(rule_id)
    return row


def create_notification_rule(
    db: PostgresDatabase,
    *,
    request: NotificationRuleCreate,
    actor: ActorIdentity,
) -> tuple[NotificationRuleRead, MutationResult]:
    rule_id = uuid4()
    persisted = request.model_dump(mode="python")

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        insert_notification_rule(connection, row={"id": rule_id, **persisted})
        return StateChangeDraft(
            change_type="notification_rule.created",
            payload_json={"rule_id": str(rule_id), **request.model_dump(mode="json")},
        )

    result = mutate_entity(
        db=db,
        aggregate_type="notification_rule",
        aggregate_id=str(rule_id),
        request=_make_request(
            expected_version=0,
            actor=actor,
            request_surface="api:/api/v1/notification-rules",
        ),
        action_type="notification_rule.create",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=RULE_PAYLOAD_FIELDS,
        mutate_projection=mutate_projection,
        scope_kind=request.scope_kind,
        scope_id=request.scope_id,
    )
    with db.connection() as connection:
        read = _rule_from_row(_fetch_rule_row(connection, rule_id))
    return read, result


def read_notification_rule(
    db: PostgresDatabase,
    *,
    rule_id: UUID,
) -> tuple[NotificationRuleRead, str]:
    with db.connection() as connection:
        read = _rule_from_row(_fetch_rule_row(connection, rule_id))
    return read, f'"{read.version}"'


def list_notification_rules(
    db: PostgresDatabase,
    *,
    scope_kind: str | None = None,
    scope_id: str | None = None,
) -> NotificationRuleListRead:
    with db.connection() as connection:
        rows = list_notification_rule_rows(
            connection,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
    return NotificationRuleListRead(items=[_rule_from_row(row) for row in rows])


def patch_notification_rule(
    db: PostgresDatabase,
    *,
    rule_id: UUID,
    patch: NotificationRulePatch,
    actor: ActorIdentity,
    expected_version: int,
) -> tuple[NotificationRuleRead, MutationResult]:
    with db.connection() as connection:
        current_row = _fetch_rule_row(connection, rule_id)
    current = _rule_from_row(current_row)
    patch_data = patch.model_dump(mode="python", exclude_unset=True)
    merged = current.model_dump(mode="python")
    merged.update(patch_data)
    merged.pop("id", None)
    merged.pop("created_at", None)
    merged.pop("updated_at", None)
    merged.pop("version", None)

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        locked_row = fetch_notification_rule_for_update(connection, rule_id)
        if locked_row is None:
            raise NotificationRuleNotFoundError(rule_id)
        updated = update_notification_rule(connection, rule_id=rule_id, patch_row=merged)
        if updated != 1:
            raise NotificationRuleNotFoundError(rule_id)
        return StateChangeDraft(
            change_type="notification_rule.updated",
            payload_json={"rule_id": str(rule_id), **NotificationRuleRead(id=rule_id, **merged, created_at=locked_row["created_at"], updated_at=locked_row["updated_at"], version=int(locked_row["version"])).model_dump(mode="json", by_alias=True)},
        )

    result = mutate_entity(
        db=db,
        aggregate_type="notification_rule",
        aggregate_id=str(rule_id),
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/notification-rules/{rule_id}",
        ),
        action_type="notification_rule.update",
        action_payload=NotificationRuleCreate.model_validate(merged).model_dump(mode="json"),
        payload_allowlist=RULE_PAYLOAD_FIELDS,
        mutate_projection=mutate_projection,
        scope_kind=merged["scope_kind"],
        scope_id=merged.get("scope_id"),
    )
    with db.connection() as connection:
        read = _rule_from_row(_fetch_rule_row(connection, rule_id))
    return read, result
