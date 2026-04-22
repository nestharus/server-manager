from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import EvidenceSubmissionCreate, EvidenceSubmissionRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.compliance import get_evidence_submission, submit_evidence

from ._shared import get_db, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("", response_model=EvidenceSubmissionRead, status_code=HTTPStatus.CREATED)
def submit_evidence_endpoint(
    body: EvidenceSubmissionCreate,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> EvidenceSubmissionRead:
    try:
        read, result = submit_evidence(db, body, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read


@router.get("/{evidence_id}", response_model=EvidenceSubmissionRead)
def get_evidence_endpoint(
    evidence_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> EvidenceSubmissionRead:
    try:
        read = get_evidence_submission(db, evidence_id=evidence_id, actor=actor)
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, f'"{read.version}"')
    return read
