from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.contracts.audit import AuditEntryListRead, AuditEntryRead
from app.core.dependencies import RequireAuthority
from app.repositories.db import PostgresDatabase
from app.services.audit import get_audit_entry
from app.services.audit_queries import (
    AuditChainTooLargeError,
    get_audit_entries_by_correlation,
    get_audit_entry_chain,
)


router = APIRouter(prefix="/api/v1/audit")


def _db(request: Request) -> PostgresDatabase:
    return request.app.state.db


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
def get_audit_entry_endpoint(
    entry_id: int,
    request: Request,
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryRead:
    try:
        return get_audit_entry(_db(request), entry_id)
    except LookupError as error:
        _raise_lookup_error(error)


@router.get("", response_model=AuditEntryListRead)
def list_audit_entries_by_correlation_endpoint(
    request: Request,
    correlation_id: str,
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryListRead:
    parsed_correlation_id = _parse_correlation_id(correlation_id)
    try:
        return get_audit_entries_by_correlation(_db(request), parsed_correlation_id)
    except AuditChainTooLargeError as error:
        _raise_chain_too_large(error)


@router.get("/{entry_id}/chain", response_model=AuditEntryListRead)
def get_audit_entry_chain_endpoint(
    entry_id: int,
    request: Request,
    _decision=Depends(RequireAuthority("audit.read", "global")),
) -> AuditEntryListRead:
    try:
        return get_audit_entry_chain(_db(request), entry_id)
    except LookupError as error:
        _raise_lookup_error(error)
    except AuditChainTooLargeError as error:
        _raise_chain_too_large(error)
