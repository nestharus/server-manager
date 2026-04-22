from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import ComplianceEvaluationRead, ComplianceEvaluationReviewRequest
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.compliance_review import get_evaluation, review_evaluation

from ._shared import get_db, parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evaluations")


@router.get("/{evaluation_id}", response_model=ComplianceEvaluationRead)
def get_evaluation_endpoint(
    evaluation_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceEvaluationRead:
    try:
        read = get_evaluation(db, evaluation_id, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, f'"{read.version}"')
    return read


@router.post("/{evaluation_id}/review", response_model=ComplianceEvaluationRead)
def review_evaluation_endpoint(
    evaluation_id: UUID,
    body: ComplianceEvaluationReviewRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceEvaluationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = review_evaluation(
            db,
            evaluation_id,
            body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
