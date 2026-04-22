from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.contracts.actor import ActorIdentity
from app.contracts.compliance_extraction import EvidenceExtractionRead
from app.core.dependencies import get_current_actor
from app.infrastructure.ocr import OcrProvider
from app.repositories.db import PostgresDatabase
from app.services.compliance_extraction import trigger_extraction

from ._shared import get_db, get_ocr_provider, raise_known_compliance_error, set_etag


router = APIRouter(prefix="/api/v1/compliance/evidence")


@router.post("/{evidence_id}/extract", response_model=EvidenceExtractionRead)
def extract_evidence_endpoint(
    evidence_id: UUID,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
    ocr_provider: OcrProvider = Depends(get_ocr_provider),
) -> EvidenceExtractionRead:
    try:
        read, result = trigger_extraction(
            db,
            evidence_id,
            actor=actor,
            ocr_provider=ocr_provider,
        )
    except Exception as error:
        raise_known_compliance_error(error)
    set_etag(response, result.etag)
    return read
