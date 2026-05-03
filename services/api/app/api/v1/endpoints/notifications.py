from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import StaleMutationError
from app.contracts.notifications import (
    NotificationRuleCreate,
    NotificationRuleListRead,
    NotificationRuleNotFoundError,
    NotificationRulePatch,
    NotificationRulePatchEmptyError,
    NotificationRuleRead,
)
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.notifications import NotificationsService


router = APIRouter(prefix="/api/v1/notification-rules")


def _parse_if_match(request: Request) -> int:
    if_match = request.headers.get("if-match")
    if if_match is None:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_REQUIRED,
            detail="If-Match header required",
        )
    if len(if_match) < 3 or not if_match.startswith('"') or not if_match.endswith('"'):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        )
    try:
        return int(if_match[1:-1])
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail="If-Match must be a strong ETag",
        ) from error


def _set_etag(response: Response, etag: str) -> None:
    response.headers["etag"] = etag


def _raise_known(error: Exception) -> None:
    if isinstance(error, NotificationRuleNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail={"code": "notification_rule_not_found", "message": str(error)},
        ) from error
    if isinstance(error, NotificationRulePatchEmptyError):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "notification_rule_patch_empty", "message": str(error)},
        ) from error
    if isinstance(error, StaleMutationError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_notification_rule_version",
                "message": str(error),
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    raise error


@router.post(
    "",
    response_model=NotificationRuleRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("notification.write", "global"))],
)
@inject
def create_notification_rule_endpoint(
    body: NotificationRuleCreate,
    response: Response,
    actor: ActorIdentity = Depends(get_current_actor),
    service: NotificationsService = Depends(
        Provide[ApiContainer.services.notifications]
    ),
) -> NotificationRuleRead:
    try:
        created, result = service.create_notification_rule(
            request=body,
            actor=actor,
        )
    except Exception as error:
        _raise_known(error)
    _set_etag(response, result.etag)
    return created


@router.get(
    "",
    response_model=NotificationRuleListRead,
    dependencies=[Depends(RequireAuthority("notification.read", "global"))],
)
@inject
def list_notification_rules_endpoint(
    scope_kind: str | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    service: NotificationsService = Depends(
        Provide[ApiContainer.services.notifications]
    ),
) -> NotificationRuleListRead:
    return service.list_notification_rules(
        scope_kind=scope_kind,
        scope_id=scope_id,
    )


@router.get(
    "/{rule_id}",
    response_model=NotificationRuleRead,
    dependencies=[Depends(RequireAuthority("notification.read", "global"))],
)
@inject
def get_notification_rule_endpoint(
    rule_id: UUID,
    response: Response,
    service: NotificationsService = Depends(
        Provide[ApiContainer.services.notifications]
    ),
) -> NotificationRuleRead:
    try:
        read, etag = service.read_notification_rule(rule_id=rule_id)
    except Exception as error:
        _raise_known(error)
    _set_etag(response, etag)
    return read


@router.patch(
    "/{rule_id}",
    response_model=NotificationRuleRead,
    dependencies=[Depends(RequireAuthority("notification.write", "global"))],
)
@inject
def patch_notification_rule_endpoint(
    rule_id: UUID,
    body: NotificationRulePatch,
    request: Request,
    response: Response,
    actor: ActorIdentity = Depends(get_current_actor),
    service: NotificationsService = Depends(
        Provide[ApiContainer.services.notifications]
    ),
) -> NotificationRuleRead:
    expected_version = _parse_if_match(request)
    try:
        read, result = service.patch_notification_rule(
            rule_id=rule_id,
            patch=body,
            actor=actor,
            expected_version=expected_version,
        )
    except Exception as error:
        _raise_known(error)
    _set_etag(response, result.etag)
    return read
