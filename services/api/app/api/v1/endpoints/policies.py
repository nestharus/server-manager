from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.contracts.actor import ActorIdentity
from app.contracts.mutations import StaleMutationError
from app.contracts.policies import (
    PolicyConfirmRequest,
    PolicyErrorBody,
    PolicyPreviewRead,
    PolicyPreviewRequest,
    PolicyPreviewTokenMismatchError,
    PolicyVersionNotFoundError,
    PolicyVersionRead,
)
from app.contracts.scope import ScopeKind
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.policies import PoliciesService


router = APIRouter(prefix="/api/v1/policies")


def _error_body(
    *,
    code: str,
    message: str,
    expected_current_version: int | None = None,
    actual_current_version: int | None = None,
) -> dict[str, object]:
    return PolicyErrorBody(
        code=code,
        message=message,
        expected_current_version=expected_current_version,
        actual_current_version=actual_current_version,
    ).model_dump(mode="json")


@router.post("/preview", response_model=PolicyPreviewRead)
@inject
def preview_policy(
    body: PolicyPreviewRequest,
    service: PoliciesService = Depends(Provide[ApiContainer.services.policies]),
    _decision=Depends(RequireAuthority("policy.write", "global")),
) -> PolicyPreviewRead:
    return service.preview(body)


@router.post("/confirm", response_model=PolicyVersionRead, status_code=HTTPStatus.CREATED)
@inject
def confirm_policy(
    body: PolicyConfirmRequest,
    response: Response,
    service: PoliciesService = Depends(Provide[ApiContainer.services.policies]),
    _decision=Depends(RequireAuthority("policy.write", "global")),
    actor: ActorIdentity = Depends(get_current_actor),
) -> PolicyVersionRead:
    try:
        created, etag = service.confirm(body, actor=actor)
    except PolicyPreviewTokenMismatchError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail=_error_body(
                code="policy_preview_token_mismatch",
                message=str(error),
            ),
        ) from error
    except StaleMutationError as error:
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail=_error_body(
                code="stale_policy_version",
                message=str(error),
                expected_current_version=error.expected_version,
                actual_current_version=error.current_version,
            ),
        ) from error

    response.headers["etag"] = etag
    return created


@router.get("/{policy_type}/current", response_model=PolicyVersionRead)
@inject
def get_current_policy(
    policy_type: str,
    response: Response,
    scope_kind: ScopeKind = Query(),
    scope_id: str | None = Query(default=None),
    service: PoliciesService = Depends(Provide[ApiContainer.services.policies]),
    _decision=Depends(RequireAuthority("policy.read", "global")),
) -> PolicyVersionRead:
    try:
        current, etag = service.get_current_policy_version(
            policy_type=policy_type,
            scope_kind=scope_kind,
            scope_id=scope_id,
        )
    except PolicyVersionNotFoundError as error:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=_error_body(
                code="policy_version_not_found",
                message=str(error),
            ),
        ) from error

    response.headers["etag"] = etag
    return current
