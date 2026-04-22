from __future__ import annotations

from fastapi import APIRouter

from . import evidence, evidence_correct, evidence_extract, evaluations, evaluations_run, rules


router = APIRouter()
router.include_router(rules.router, tags=["compliance-rules"])
router.include_router(evidence.router, tags=["compliance-evidence"])
router.include_router(evidence_correct.router, tags=["compliance-evidence"])
router.include_router(evidence_extract.router, tags=["compliance-evidence"])
router.include_router(evaluations.router, tags=["compliance-evaluations"])
router.include_router(evaluations_run.router, tags=["compliance-evaluations"])

__all__ = ["router"]
