from __future__ import annotations

from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import ComplianceEvaluationRead, ComplianceEvaluationReviewRequest
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.services.compliance_review import ComplianceReviewService

from ._shared import parse_if_match_strong, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evaluations")


@router.get("/{evaluation_id}", response_model=ComplianceEvaluationRead)
@inject
def get_evaluation_endpoint(
    evaluation_id: UUID,
    response: Response,
    service: ComplianceReviewService = Depends(
        Provide[ApiContainer.services.compliance_review]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceEvaluationRead:
    try:
        read = service.get_evaluation(evaluation_id, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, f'"{read.version}"')
    return read


@router.post("/{evaluation_id}/review", response_model=ComplianceEvaluationRead)
@inject
def review_evaluation_endpoint(
    evaluation_id: UUID,
    body: ComplianceEvaluationReviewRequest,
    request: Request,
    response: Response,
    service: ComplianceReviewService = Depends(
        Provide[ApiContainer.services.compliance_review]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ComplianceEvaluationRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.review_evaluation(
            evaluation_id,
            body,
            expected_version=expected_version,
            actor=actor,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
