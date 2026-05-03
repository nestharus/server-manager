from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.v1.endpoints.chapters.base import (
    get_db,
    parse_if_match,
    raise_for_chapter_error,
    set_etag,
)
from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityRequirement
from app.contracts.chapters import ChapterGovernanceTransitionRequest, ChapterRead
from app.core.container import ApiContainer
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.authority import current_time, evaluate, list_grants_for_grantee
from app.services.chapters import ChaptersService

router = APIRouter(prefix="/api/v1/chapters")


def _require_governance_authority(
    *,
    db: PostgresDatabase,
    actor: ActorIdentity,
    chapter_id: str,
    permission: str,
) -> None:
    grants = list_grants_for_grantee(db, grantee_id=actor.actor_id)
    decision = evaluate(
        requirement=AuthorityRequirement(
            scope_kind="chapter",
            scope_id=chapter_id,
            permission=permission,
        ),
        grants=grants,
        at=current_time(),
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "authority_decision_denied",
                "message": "authority requirement denied",
                "decision": decision.model_dump(mode="json"),
            },
        )


@router.post(
    "/{chapter_id}/governance-transitions",
    response_model=ChapterRead,
)
@inject
def governance_transition(
    chapter_id: UUID,
    transition: ChapterGovernanceTransitionRequest,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    service: ChaptersService = Depends(Provide[ApiContainer.services.chapters]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterRead:
    permission = (
        "chapter.archive" if transition.action == "archive" else "chapter.governance"
    )
    _require_governance_authority(
        db=db,
        actor=actor,
        chapter_id=str(chapter_id),
        permission=permission,
    )
    expected_version = parse_if_match(request)
    try:
        read, result = service.governance_transition(
            str(chapter_id),
            expected_version,
            transition,
            actor,
        )
    except Exception as error:
        raise_for_chapter_error(error)
    set_etag(response, result.etag)
    return read


__all__ = ["router"]
