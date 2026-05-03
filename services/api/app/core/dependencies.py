from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Request

from app.contracts.actor import ActorIdentity, ActorIdentityMissingError
from app.contracts.authority import (
    AuthorityDecisionRead,
    AuthorityErrorBody,
    AuthorityRequirement,
)
from app.contracts.scope import ScopeKind
from app.core.container import ApiContainer
from app.core.context import get_current_actor as _get_current_actor
from app.repositories.authority import AuthorityRepository
from app.services.audit_overrides import AuditOverridesService
from app.services.authority import current_time, evaluate, _row_to_read


def _authority_error(
    *,
    status_code: int,
    code: str,
    message: str,
    decision: AuthorityDecisionRead | None = None,
) -> HTTPException:
    body = AuthorityErrorBody(code=code, message=message, decision=decision)
    return HTTPException(status_code=status_code, detail=body.model_dump(mode="json"))


def _normalize_override_reason(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    trimmed = raw_value.strip()
    if not trimmed:
        return None
    if len(trimmed) > 512:
        raise _authority_error(
            status_code=HTTPStatus.BAD_REQUEST,
            code="invalid_override_reason",
            message="X-Override-Reason must be 512 characters or fewer",
        )
    return trimmed


def get_current_actor() -> ActorIdentity:
    try:
        return _get_current_actor()
    except ActorIdentityMissingError as error:
        raise _authority_error(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="actor_identity_missing",
            message=error.message,
        ) from error


class _RequireAuthority:
    def __init__(
        self,
        *,
        permission: str,
        scope_kind: ScopeKind,
        scope_id_param: str | None = None,
    ) -> None:
        self._permission = permission
        self._scope_kind = scope_kind
        self._scope_id_param = scope_id_param

    @inject
    def __call__(
        self,
        request: Request,
        authority_repo: AuthorityRepository = Depends(
            Provide[ApiContainer.repos.authority]
        ),
        audit_overrides_service: AuditOverridesService = Depends(
            Provide[ApiContainer.services.audit_overrides]
        ),
    ) -> AuthorityDecisionRead:
        actor = get_current_actor()
        scope_id = None
        if self._scope_id_param is not None:
            scope_id = request.path_params.get(self._scope_id_param)

        requirement = AuthorityRequirement(
            scope_kind=self._scope_kind,
            scope_id=scope_id,
            permission=self._permission,
        )
        grants = [
            _row_to_read(row)
            for row in authority_repo.list_grants(
                grantee_id=actor.actor_id,
                include_revoked=True,
                limit=None,
                after_id=None,
            )
        ]
        decision = evaluate(requirement=requirement, grants=grants, at=current_time())
        override_reason = _normalize_override_reason(
            request.headers.get("X-Override-Reason")
        )

        if decision.allowed:
            return decision

        if override_reason is None:
            raise _authority_error(
                status_code=HTTPStatus.FORBIDDEN,
                code="authority_decision_denied",
                message="authority requirement denied",
                decision=decision,
            )

        override_requirement = AuthorityRequirement(
            scope_kind="global",
            scope_id=None,
            permission=self._permission,
        )
        override_decision = evaluate(
            requirement=override_requirement,
            grants=grants,
            at=current_time(),
        )
        if not override_decision.allowed:
            raise _authority_error(
                status_code=HTTPStatus.FORBIDDEN,
                code="authority_decision_denied",
                message="authority requirement denied",
                decision=decision,
            )

        audit_overrides_service.record_authority_override(
            actor=actor,
            requirement=requirement,
            reason=override_reason,
        )
        return AuthorityDecisionRead(
            allowed=True,
            grant_id=override_decision.grant_id,
            denial_reason=None,
            override_used=True,
        )


def RequireAuthority(
    permission: str,
    scope_kind: ScopeKind,
    scope_id_param: str | None = None,
) -> _RequireAuthority:
    return _RequireAuthority(
        permission=permission,
        scope_kind=scope_kind,
        scope_id_param=scope_id_param,
    )
