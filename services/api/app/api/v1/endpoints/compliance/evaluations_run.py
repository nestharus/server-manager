from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.contracts.actor import ActorIdentity
from app.contracts.compliance import ComplianceEvaluationRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services._helpers.authority import _require_scoped_authority
from app.services.compliance import compliance_evaluator_actor, run_scheduled_compliance_evaluations

from ._shared import get_db, raise_known_compliance_error


router = APIRouter(prefix="/api/v1/compliance/evaluations")


@router.post("/run", response_model=list[ComplianceEvaluationRead])
def run_compliance_evaluations_endpoint(
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> list[ComplianceEvaluationRead]:
    try:
        _require_scoped_authority(
            "compliance_evaluation.write",
            scope_kind="global",
            scope_id=None,
            actor=actor,
            db=db,
        )
        return run_scheduled_compliance_evaluations(
            db,
            now=datetime.now(tz=UTC),
            actor=compliance_evaluator_actor(),
            originating_actor=actor,
            source="manual_trigger",
        )
    except Exception as error:
        raise_known_compliance_error(error)
