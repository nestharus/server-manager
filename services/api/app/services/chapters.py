from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChapterTemplateNotFoundError,
    TemplateSchemaVersionMismatchError,
)
from app.contracts.chapters import (
    ChapterCreate,
    ChapterDiscordResources,
    ChapterDuplicateNameError,
    ChapterNotFoundError,
    ChapterRead,
    ChapterResourcesPatchRequest,
    ChapterTransitionRequest,
    IncompleteProvisioningError,
    InvalidChapterTransitionError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.scheduler import DeferredEffectCreate
from app.core.context import get_current_audit_context
from app.repositories.chapter_templates import fetch_chapter_template
from app.repositories.chapter_transitions import insert_chapter_transition
from app.repositories.chapters import (
    fetch_chapter,
    fetch_chapter_for_update,
    insert_chapter,
    merge_chapter_discord_resources,
    update_chapter_state,
)
from app.repositories.db import PostgresDatabase
from app.repositories.deferred_effects import enqueue_effect
from app.services.mutations import mutate_entity
from app.services.scheduler import DEFAULT_MAX_ATTEMPTS


VALID_TRANSITIONS = {
    ("proposed", "provisioning"),
    ("provisioning", "active"),
    ("provisioning", "provisioning_failed"),
    ("provisioning_failed", "provisioning"),
}


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
    reason_text: str | None = None,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=reason_text,
        request_surface=request_surface,
    )


def _chapter_from_row(row: dict[str, Any]) -> ChapterRead:
    return ChapterRead(
        id=row["id"],
        name=row["name"],
        template_id=row["template_id"],
        template_snapshot=row["template_snapshot"],
        configuration=row["configuration"],
        state=row["state"],
        discord_resources=ChapterDiscordResources.model_validate(
            row["discord_resources"]
        ),
        created_at=row["created_at"],
        version=int(row["version"]),
    )


def _fetch_chapter_row(connection: Connection[Any], chapter_id: str) -> dict[str, Any]:
    row = fetch_chapter(connection, chapter_id)
    if row is None:
        raise ChapterNotFoundError(chapter_id)
    return row


def _build_template_snapshot(template: dict[str, Any]) -> dict[str, Any]:
    if int(template["schema_version"]) != CURRENT_TEMPLATE_SCHEMA_VERSION:
        raise TemplateSchemaVersionMismatchError(int(template["schema_version"]))
    return {
        "template_id": str(template["id"]),
        "template_family_id": str(template["template_family_id"]),
        "template_version": int(template["version"]),
        "schema_version": int(template["schema_version"]),
        "channel_structure": deepcopy(template["channel_structure"]),
        "role_structure": deepcopy(template["role_structure"]),
        "default_permission_intents": deepcopy(template["default_permission_intents"]),
    }


def create_chapter(
    db: PostgresDatabase,
    request: ChapterCreate,
    actor: ActorIdentity,
) -> tuple[ChapterRead, MutationResult]:
    chapter_id = str(uuid4())
    initial_resources = {"category_id": None, "role_ids": {}, "channel_ids": {}}

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        template = fetch_chapter_template(connection, request.template_id)
        if template is None:
            raise ChapterTemplateNotFoundError(request.template_id)
        snapshot = _build_template_snapshot(template)
        insert_chapter(
            connection,
            row={
                "id": chapter_id,
                "name": request.name,
                "template_id": request.template_id,
                "template_snapshot": snapshot,
                "configuration": request.configuration,
                "state": "proposed",
                "discord_resources": initial_resources,
            },
        )
        payload = {
            "chapter_id": chapter_id,
            "name": request.name,
            "template_id": str(request.template_id),
            "template_snapshot": snapshot,
            "configuration": request.configuration,
            "state": "proposed",
            "discord_resources": initial_resources,
            "originating_actor_kind": request.originating_actor_kind,
            "originating_actor_id": request.originating_actor_id,
        }
        if request.originating_actor_kind == "user":
            payload["originating_user_discord_id"] = request.originating_actor_id
        return StateChangeDraft(
            change_type="chapter.created",
            payload_json=payload,
        )

    try:
        result = mutate_entity(
            db=db,
            aggregate_type="chapter",
            aggregate_id=chapter_id,
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="api:/api/v1/chapters",
            ),
            action_type="chapter.create",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump(mode="json").keys()),
            mutate_projection=mutate_projection,
        )
    except errors.UniqueViolation as error:
        raise ChapterDuplicateNameError(request.name) from error

    with db.connection() as connection:
        read = _chapter_from_row(_fetch_chapter_row(connection, chapter_id))
    return read, result


def read_chapter(
    db: PostgresDatabase,
    chapter_id: str,
) -> tuple[ChapterRead, str]:
    with db.connection() as connection:
        read = _chapter_from_row(_fetch_chapter_row(connection, chapter_id))
    return read, f'"{read.version}"'


def _verify_transition(*, chapter_id: str, from_state: str, to_state: str) -> None:
    if (from_state, to_state) not in VALID_TRANSITIONS:
        raise InvalidChapterTransitionError(
            chapter_id=chapter_id,
            from_state=from_state,
            to_state=to_state,
        )


def _expected_names(snapshot: dict[str, Any], key: str) -> set[str]:
    return {str(item["name"]) for item in snapshot.get(key, [])}


def _verify_provisioning_complete(chapter: dict[str, Any]) -> None:
    snapshot = chapter["template_snapshot"]
    resources = chapter["discord_resources"]

    if not resources.get("category_id"):
        raise IncompleteProvisioningError(missing="category")

    expected_role_names = _expected_names(snapshot, "role_structure")
    present_role_names = set(resources.get("role_ids", {}).keys())
    missing_roles = expected_role_names - present_role_names
    if missing_roles:
        raise IncompleteProvisioningError(missing=f"roles:{sorted(missing_roles)}")

    expected_channel_names = _expected_names(snapshot, "channel_structure")
    present_channel_names = set(resources.get("channel_ids", {}).keys())
    missing_channels = expected_channel_names - present_channel_names
    if missing_channels:
        raise IncompleteProvisioningError(missing=f"channels:{sorted(missing_channels)}")


def _merge_resources(
    current: dict[str, Any],
    patch: ChapterDiscordResources,
) -> dict[str, Any]:
    merged = {
        "category_id": current.get("category_id"),
        "role_ids": dict(current.get("role_ids", {})),
        "channel_ids": dict(current.get("channel_ids", {})),
    }
    if patch.category_id is not None:
        merged["category_id"] = patch.category_id
    merged["role_ids"].update(patch.role_ids)
    merged["channel_ids"].update(patch.channel_ids)
    return merged


def patch_chapter_discord_resources(
    db: PostgresDatabase,
    chapter_id: str,
    request: ChapterResourcesPatchRequest,
    actor: ActorIdentity,
    expected_version: int,
) -> tuple[ChapterRead, MutationResult]:
    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = fetch_chapter_for_update(connection, chapter_id)
        if row is None:
            raise ChapterNotFoundError(chapter_id)
        merged = _merge_resources(row["discord_resources"], request.resources)
        merge_chapter_discord_resources(
            connection,
            chapter_id=chapter_id,
            resources=merged,
        )
        return StateChangeDraft(
            change_type="chapter.discord_resources_patched",
            payload_json={
                "chapter_id": chapter_id,
                "discord_resources": merged,
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="chapter",
        aggregate_id=chapter_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/chapters/{chapter_id}/discord-resources",
        ),
        action_type="chapter.discord_resources.patch",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump(mode="json").keys()),
        mutate_projection=mutate_projection,
    )
    with db.connection() as connection:
        read = _chapter_from_row(_fetch_chapter_row(connection, chapter_id))
    return read, result


def _enqueue_failed_provisioning_effect(
    connection: Connection[Any],
    *,
    chapter_id: str,
    chapter_transition_id: Any,
    chapter: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    ctx = get_current_audit_context()
    if ctx is None:
        raise RuntimeError("missing audit context for deferred effect enqueue")
    effect = DeferredEffectCreate(
        subsystem="chapter_provisioning",
        effect_type="chapter_provisioning_retry",
        idempotency_key=(
            f"chapter_provision_retry:{chapter_id}:{chapter_transition_id}"
        ),
        payload_json={
            "chapter_id": chapter_id,
            "template_id": str(chapter["template_id"]),
            "partial_resources": chapter["discord_resources"],
            "failure_reason": reason,
            "failed_at_step": "api_confirm",
        },
        consequence_level="consequential",
        correlation_id=ctx.correlation_id,
    )
    return enqueue_effect(
        connection,
        effect=effect,
        correlation_id=ctx.correlation_id,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )


def transition_chapter(
    db: PostgresDatabase,
    chapter_id: str,
    request: ChapterTransitionRequest,
    actor: ActorIdentity,
    expected_version: int,
) -> tuple[ChapterRead, MutationResult]:
    transition_id = uuid4()

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        row = fetch_chapter_for_update(connection, chapter_id)
        if row is None:
            raise ChapterNotFoundError(chapter_id)
        from_state = row["state"]
        _verify_transition(
            chapter_id=chapter_id,
            from_state=from_state,
            to_state=request.to_state,
        )
        if request.to_state == "active":
            _verify_provisioning_complete(row)

        aggregate_seq = expected_version + 1
        insert_chapter_transition(
            connection,
            row={
                "id": transition_id,
                "chapter_id": chapter_id,
                "aggregate_seq": aggregate_seq,
                "from_state": from_state,
                "to_state": request.to_state,
                "actor_kind": actor.actor_kind,
                "actor_id": actor.actor_id,
                "originating_actor_kind": request.originating_actor_kind,
                "originating_actor_id": request.originating_actor_id,
                "reason": request.reason,
            },
        )
        update_chapter_state(
            connection,
            chapter_id=chapter_id,
            state=request.to_state,
        )
        payload: dict[str, Any] = {
            "chapter_transition_id": str(transition_id),
            "chapter_id": chapter_id,
            "from_state": from_state,
            "to_state": request.to_state,
            "reason": request.reason,
            "originating_actor_kind": request.originating_actor_kind,
            "originating_actor_id": request.originating_actor_id,
        }
        if request.originating_actor_kind == "user":
            payload["originating_user_discord_id"] = request.originating_actor_id
        if request.to_state == "provisioning_failed":
            updated = dict(row)
            updated["state"] = request.to_state
            effect_row = _enqueue_failed_provisioning_effect(
                connection,
                chapter_id=chapter_id,
                chapter_transition_id=transition_id,
                chapter=updated,
                reason=request.reason,
            )
            payload["deferred_effect_id"] = str(effect_row["id"])
            payload["deferred_effect_idempotency_key"] = effect_row["idempotency_key"]
        return StateChangeDraft(
            change_type="chapter.transitioned",
            payload_json=payload,
            diff_json={
                "state": {"old": from_state, "new": request.to_state},
            },
        )

    result = mutate_entity(
        db=db,
        aggregate_type="chapter",
        aggregate_id=chapter_id,
        request=_make_request(
            expected_version=expected_version,
            actor=actor,
            request_surface=f"api:/api/v1/chapters/{chapter_id}/transitions",
            reason_text=request.reason,
        ),
        action_type="chapter.transition",
        action_payload=request.model_dump(mode="json"),
        payload_allowlist=set(request.model_dump(mode="json").keys()),
        mutate_projection=mutate_projection,
    )
    with db.connection() as connection:
        read = _chapter_from_row(_fetch_chapter_row(connection, chapter_id))
    return read, result


__all__ = [
    "create_chapter",
    "patch_chapter_discord_resources",
    "read_chapter",
    "transition_chapter",
]
