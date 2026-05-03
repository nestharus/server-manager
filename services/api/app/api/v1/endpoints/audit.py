from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from app.contracts.audit import AuditEntryListRead, AuditEntryRead
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority
from app.services.audit import AuditService
from app.services.audit_queries import (
    AuditChainTooLargeError,
    AuditQueriesService,
)


router = APIRouter(prefix="/api/v1/audit")


def _error_body(*, code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _parse_correlation_id(raw_value: str) -> UUID:
    try:
        return UUID(raw_value)
    except ValueError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=_error_body(
                code="invalid_correlation_id",
                message="correlation_id must be a valid UUID",
            ),
        ) from error


def _raise_lookup_error(error: LookupError) -> None:
    raise HTTPException(
        status_code=HTTPStatus.NOT_FOUND,
        detail=_error_body(code="audit_entry_not_found", message=str(error)),
    ) from error


def _raise_chain_too_large(error: AuditChainTooLargeError) -> None:
    raise HTTPException(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        detail=_error_body(code="audit_chain_too_large", message=str(error)),
    ) from error


@router.get("/{entry_id}", response_model=AuditEntryRead)
@inject
def get_audit_entry_endpoint(
    entry_id: int,
    service: AuditService = Depends(Provide[ApiContainer.services.audit]),
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryRead:
    try:
        return service.get_audit_entry(entry_id)
    except LookupError as error:
        _raise_lookup_error(error)


@router.get("", response_model=AuditEntryListRead)
@inject
def list_audit_entries_by_correlation_endpoint(
    correlation_id: str,
    service: AuditQueriesService = Depends(
        Provide[ApiContainer.services.audit_queries]
    ),
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryListRead:
    parsed_correlation_id = _parse_correlation_id(correlation_id)
    try:
        return service.get_audit_entries_by_correlation(parsed_correlation_id)
    except AuditChainTooLargeError as error:
        _raise_chain_too_large(error)


@router.get("/{entry_id}/chain", response_model=AuditEntryListRead)
@inject
def get_audit_entry_chain_endpoint(
    entry_id: int,
    service: AuditQueriesService = Depends(
        Provide[ApiContainer.services.audit_queries]
    ),
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryListRead:
    try:
        return service.get_audit_entry_chain(entry_id)
    except LookupError as error:
        _raise_lookup_error(error)
    except AuditChainTooLargeError as error:
        _raise_chain_too_large(error)
