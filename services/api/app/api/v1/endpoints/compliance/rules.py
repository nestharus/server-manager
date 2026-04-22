from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import ComplianceRuleCreate, ComplianceRuleRead, ComplianceRuleUpdate
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.compliance import create_rule, list_rules, update_rule

from ._shared import get_db, parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/rules")


@router.post("", response_model=ComplianceRuleRead, status_code=HTTPStatus.CREATED)
def create_rule_endpoint(
    body: ComplianceRuleCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceRuleRead:
    try:
        read, result = create_rule(db, body, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read


@router.patch("/{rule_id}", response_model=ComplianceRuleRead)
def update_rule_endpoint(
    rule_id: UUID,
    body: ComplianceRuleUpdate,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceRuleRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = update_rule(
            db,
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
def list_rules_endpoint(
    chapter_id: str = Query(..., min_length=1),
    active_only: bool = True,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[ComplianceRuleRead]:
    try:
        return list_rules(
            db,
            chapter_id=chapter_id,
            active_only=active_only,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
