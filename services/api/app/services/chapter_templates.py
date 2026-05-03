from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.chapter_templates import (
    CURRENT_TEMPLATE_SCHEMA_VERSION,
    ChapterTemplateCreate,
    ChapterTemplateNotFoundError,
    ChapterTemplatePatch,
    ChapterTemplateRead,
    StaleTemplateVersionError,
    TemplateSchemaVersionMismatchError,
)
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.repositories.chapter_templates import ChapterTemplatesRepository


def _system_actor() -> ActorIdentity:
    return ActorIdentity(actor_kind="system", actor_id="chapter-templates-service")


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


def _validate_schema_version(schema_version: int) -> None:
    if schema_version != CURRENT_TEMPLATE_SCHEMA_VERSION:
        raise TemplateSchemaVersionMismatchError(schema_version)


def _row_to_read(row: dict[str, Any]) -> ChapterTemplateRead:
    _validate_schema_version(int(row["schema_version"]))
    return ChapterTemplateRead.model_validate(row)


class ChapterTemplatesService:
    def __init__(
        self,
        chapter_templates_repo: ChapterTemplatesRepository,
        mutations_callable,
    ) -> None:
        self._chapter_templates_repo = chapter_templates_repo
        self._mutations_callable = mutations_callable

    def create_chapter_template(
        self,
        request: ChapterTemplateCreate,
        actor: ActorIdentity | None = None,
    ) -> tuple[ChapterTemplateRead, MutationResult]:
        resolved_actor = actor if actor is not None else _system_actor()
        template_id = uuid4()
        template_row = {
            "id": template_id,
            "template_family_id": template_id,
            "version": 1,
            **request.model_dump(mode="python"),
        }

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._chapter_templates_repo._insert_chapter_template_on(
                connection,
                row=template_row,
            )
            return StateChangeDraft(
                change_type="chapter_template.created",
                payload_json={
                    **ChapterTemplateRead(
                        id=template_id,
                        template_family_id=template_id,
                        version=1,
                        created_at=requested_at(),
                        **request.model_dump(mode="python"),
                    ).model_dump(mode="json")
                },
            )

        result = self._mutations_callable(
            aggregate_type="chapter_template",
            aggregate_id=str(template_id),
            request=_make_request(
                expected_version=0,
                actor=resolved_actor,
                request_surface="api:/api/v1/chapter-templates",
            ),
            action_type="chapter_template.create",
            action_payload=request.model_dump(mode="json"),
            payload_allowlist=set(request.model_dump().keys()),
            mutate_projection=mutate_projection,
        )
        with self._chapter_templates_repo.db.connection() as connection:
            read = _row_to_read(self._fetch_template_row_on(connection, template_id))
        return read, result

    def _fetch_template_row_on(
        self,
        connection: Connection[Any],
        template_id: UUID,
    ) -> dict[str, Any]:
        row = self._chapter_templates_repo._fetch_chapter_template_on(
            connection,
            template_id,
        )
        if row is None:
            raise ChapterTemplateNotFoundError(template_id)
        return row

    def read_chapter_template(self, template_id: UUID) -> ChapterTemplateRead:
        with self._chapter_templates_repo.db.connection() as connection:
            return _row_to_read(self._fetch_template_row_on(connection, template_id))

    def patch_chapter_template(
        self,
        template_id: UUID,
        request: ChapterTemplatePatch,
        actor: ActorIdentity,
    ) -> tuple[ChapterTemplateRead, MutationResult]:
        new_template_id = uuid4()
        new_row: dict[str, Any] = {}

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            source = self._chapter_templates_repo._fetch_chapter_template_for_update_on(
                connection,
                template_id,
            )
            if source is None:
                raise ChapterTemplateNotFoundError(template_id)
            current_version = self._chapter_templates_repo._fetch_current_template_family_version_for_update_on(
                connection,
                source["template_family_id"],
            )
            if current_version is None:
                raise ChapterTemplateNotFoundError(template_id)
            if request.expected_current_version != current_version:
                raise StaleTemplateVersionError(
                    template_family_id=source["template_family_id"],
                    expected_version=request.expected_current_version,
                    current_version=current_version,
                )
            latest = self._chapter_templates_repo._fetch_latest_template_family_version_for_update_on(
                connection,
                source["template_family_id"],
            )
            if latest is None:
                raise ChapterTemplateNotFoundError(template_id)

            patch = request.model_dump(exclude_unset=True, mode="python")
            patch.pop("expected_current_version", None)
            schema_version = (
                patch.pop("schema_version", None) or CURRENT_TEMPLATE_SCHEMA_VERSION
            )

            new_row.update(
                {
                    "id": new_template_id,
                    "template_family_id": latest["template_family_id"],
                    "version": current_version + 1,
                    "name": patch.get("name", latest["name"]),
                    "schema_version": schema_version,
                    "channel_structure": patch.get(
                        "channel_structure",
                        latest["channel_structure"],
                    ),
                    "role_structure": patch.get(
                        "role_structure",
                        latest["role_structure"],
                    ),
                    "default_permission_intents": patch.get(
                        "default_permission_intents",
                        latest["default_permission_intents"],
                    ),
                }
            )
            self._chapter_templates_repo._insert_template_version_on(
                connection,
                row=new_row,
            )
            return StateChangeDraft(
                change_type="chapter_template.version_created",
                payload_json={
                    "template_id": str(new_template_id),
                    "template_family_id": str(new_row["template_family_id"]),
                    "version": new_row["version"],
                    "source_template_id": str(template_id),
                },
            )

        try:
            result = self._mutations_callable(
                aggregate_type="chapter_template",
                aggregate_id=str(new_template_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface=f"api:/api/v1/chapter-templates/{template_id}",
                ),
                action_type="chapter_template.patch",
                action_payload=request.model_dump(mode="json"),
                payload_allowlist=set(request.model_dump(mode="json").keys()),
                mutate_projection=mutate_projection,
            )
        except errors.UniqueViolation as error:
            with self._chapter_templates_repo.db.connection() as connection:
                source = self._fetch_template_row_on(connection, template_id)
                current_version = self._chapter_templates_repo._fetch_current_template_family_version_for_update_on(
                    connection,
                    source["template_family_id"],
                )
            raise StaleTemplateVersionError(
                template_family_id=source["template_family_id"],
                expected_version=request.expected_current_version,
                current_version=current_version or request.expected_current_version,
            ) from error

        with self._chapter_templates_repo.db.connection() as connection:
            read = _row_to_read(
                self._fetch_template_row_on(connection, new_template_id)
            )
        return read, result


def requested_at() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)


__all__ = ["ChapterTemplatesService"]
