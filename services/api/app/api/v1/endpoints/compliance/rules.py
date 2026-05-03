from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import ComplianceRuleCreate, ComplianceRuleRead, ComplianceRuleUpdate
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.compliance import ComplianceService

from ._shared import parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/rules")


@router.post("", response_model=ComplianceRuleRead, status_code=HTTPStatus.CREATED)
@inject
def create_rule_endpoint(
    body: ComplianceRuleCreate,
    response: Response,
    service: ComplianceService = Depends(Provide[ApiContainer.services.compliance]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceRuleRead:
    try:
        read, result = service.create_rule(body, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read


@router.patch("/{rule_id}", response_model=ComplianceRuleRead)
@inject
def update_rule_endpoint(
    rule_id: UUID,
    body: ComplianceRuleUpdate,
    request: Request,
    response: Response,
    service: ComplianceService = Depends(Provide[ApiContainer.services.compliance]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceRuleRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.update_rule(
            rule_id,
            body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read


@router.get("", response_model=list[ComplianceRuleRead])
@inject
def list_rules_endpoint(
    chapter_id: str = Query(..., min_length=1),
    active_only: bool = True,
    service: ComplianceService = Depends(Provide[ApiContainer.services.compliance]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[ComplianceRuleRead]:
    try:
        return service.list_rules(
            chapter_id=chapter_id,
            active_only=active_only,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
