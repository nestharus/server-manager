from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, Error as PsycopgError

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationRead
from app.contracts.mutations import MutationRequest, MutationResult, StateChangeDraft
from app.contracts.notifications import (
    NotificationEventDraft,
    NotificationRuleCreate,
    NotificationRuleListRead,
    NotificationRuleNotFoundError,
    NotificationRulePatch,
    NotificationRuleRead,
)
from app.core.settings import Settings
from app.repositories.chapters import ChaptersRepository
from app.repositories.notifications import NotificationsRepository
from app.services.application_public_submit_notifications import (
    build_application_public_submit_payload,
)
from app.services.notification_events import NotificationEventsService

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
APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST = frozenset(
    {
        "application_id",
        "support_id",
        "recipient_discord_user_id",
        "scope_kind",
        "scope_id",
        "scope_label",
        "submitted_unix_ts",
        "submitted_iso",
        "form_version",
        "character_name",
        "response_preview",
        "application_url",
        "officer_review_channel_id",
        "application_managers_role_id",
        "application_managers_role_mention",
        "primary_guild_channel_url",
    }
)


class NotificationEmitError(Exception):
    pass


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


class NotificationsService:
    def __init__(
        self,
        notifications_repo: NotificationsRepository,
        notification_events_service: NotificationEventsService,
        mutations_callable,
    ) -> None:
        self._notifications_repo = notifications_repo
        self._notification_events_service = notification_events_service
        self._mutations_callable = mutations_callable

    def emit_application_public_submitted_event(
        self,
        *,
        application: ApplicationRead,
        discord_user_id: str,
    ) -> None:
        settings = Settings()
        db = self._notifications_repo.db
        chapter_discord_resources: dict[str, Any] | None = None
        scope_kind = application.target_scope.scope_kind
        scope_id = application.target_scope.scope_id

        try:
            with db.transaction() as connection:
                if scope_kind == "chapter" and scope_id is not None:
                    chapter = ChaptersRepository(db)._fetch_chapter_on(
                        connection,
                        chapter_id=scope_id,
                    )
                    if chapter is not None:
                        chapter_discord_resources = chapter["discord_resources"]

                payload = build_application_public_submit_payload(
                    application=application,
                    recipient_discord_user_id=discord_user_id,
                    web_public_base_url=settings.web_public_base_url,
                    global_applications_review_channel_id=settings.global_applications_review_channel_id,
                    global_application_managers_role_id=settings.global_application_managers_role_id,
                    global_primary_guild_channel_url=settings.global_primary_guild_channel_url,
                    chapter_discord_resources=chapter_discord_resources,
                )
                if payload is None:
                    return

                self._notification_events_service.emit(
                    connection,
                    event=NotificationEventDraft(
                        event_type="application.public_submitted",
                        scope_kind=scope_kind,
                        scope_id=scope_id,
                        payload_json=payload,
                    ),
                    actor=ActorIdentity(actor_kind="service", actor_id="notifications"),
                    payload_allowlist=APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST,
                )
        except PsycopgError as error:
            raise NotificationEmitError(
                "application public-submit notification emit failed"
            ) from error

    def create_notification_rule(
        self,
        *,
        request: NotificationRuleCreate,
        actor: ActorIdentity,
    ) -> tuple[NotificationRuleRead, MutationResult]:
        rule_id = uuid4()
        persisted = request.model_dump(mode="python")

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._notifications_repo._insert_notification_rule_on(
                connection,
                row={"id": rule_id, **persisted},
            )
            return StateChangeDraft(
                change_type="notification_rule.created",
                payload_json={
                    "rule_id": str(rule_id),
                    **request.model_dump(mode="json"),
                },
            )

        result = self._mutations_callable(
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
        read = _rule_from_row(self._fetch_rule_row(rule_id))
        return read, result

    def read_notification_rule(
        self, *, rule_id: UUID
    ) -> tuple[NotificationRuleRead, str]:
        read = _rule_from_row(self._fetch_rule_row(rule_id))
        return read, f'"{read.version}"'

    def list_notification_rules(
        self,
        *,
        scope_kind: str | None = None,
        scope_id: str | None = None,
    ) -> NotificationRuleListRead:
        rows = self._notifications_repo.list_notification_rules(
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
        return NotificationRuleListRead(items=[_rule_from_row(row) for row in rows])

    def patch_notification_rule(
        self,
        *,
        rule_id: UUID,
        patch: NotificationRulePatch,
        actor: ActorIdentity,
        expected_version: int,
    ) -> tuple[NotificationRuleRead, MutationResult]:
        current = _rule_from_row(self._fetch_rule_row(rule_id))
        patch_data = patch.model_dump(mode="python", exclude_unset=True)
        merged = current.model_dump(mode="python")
        merged.update(patch_data)
        merged.pop("id", None)
        merged.pop("created_at", None)
        merged.pop("updated_at", None)
        merged.pop("version", None)

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            locked_row = (
                self._notifications_repo._fetch_notification_rule_for_update_on(
                    connection,
                    rule_id,
                )
            )
            if locked_row is None:
                raise NotificationRuleNotFoundError(rule_id)
            updated_row = self._notifications_repo._update_notification_rule_on(
                connection,
                rule_id=rule_id,
                patch_row=merged,
            )
            if updated_row is None:
                raise NotificationRuleNotFoundError(rule_id)
            updated_read = NotificationRuleRead(
                id=rule_id,
                **merged,
                created_at=locked_row["created_at"],
                updated_at=updated_row["updated_at"],
                version=int(locked_row["version"]) + 1,
            )
            return StateChangeDraft(
                change_type="notification_rule.updated",
                payload_json={
                    "rule_id": str(rule_id),
                    **updated_read.model_dump(mode="json", by_alias=True),
                },
            )

        result = self._mutations_callable(
            aggregate_type="notification_rule",
            aggregate_id=str(rule_id),
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/notification-rules/{rule_id}",
            ),
            action_type="notification_rule.patch",
            action_payload=NotificationRuleCreate.model_validate(merged).model_dump(
                mode="json"
            ),
            payload_allowlist=RULE_PAYLOAD_FIELDS,
            mutate_projection=mutate_projection,
            scope_kind=merged["scope_kind"],
            scope_id=merged.get("scope_id"),
        )
        read = _rule_from_row(self._fetch_rule_row(rule_id))
        return read, result

    def _fetch_rule_row(self, rule_id: UUID) -> dict[str, Any]:
        row = self._notifications_repo.fetch_notification_rule(rule_id)
        if row is None:
            raise NotificationRuleNotFoundError(rule_id)
        return row


__all__ = [
    "APPLICATION_PUBLIC_SUBMITTED_PAYLOAD_ALLOWLIST",
    "NotificationEmitError",
    "NotificationsService",
]
