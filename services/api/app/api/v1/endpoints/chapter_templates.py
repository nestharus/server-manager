"""Chapter template management endpoints."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Response

from app.contracts.actor import ActorIdentity
from app.contracts.chapter_templates import (
    ChapterTemplateCreate,
    ChapterTemplateNotFoundError,
    ChapterTemplatePatch,
    ChapterTemplateRead,
    StaleTemplateVersionError,
    TemplateSchemaVersionMismatchError,
)
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.chapter_templates import ChapterTemplatesService

router = APIRouter(prefix="/api/v1/chapter-templates")


def _raise_for_template_error(error: Exception) -> None:
    if isinstance(error, ChapterTemplateNotFoundError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="not found"
        ) from error
    if isinstance(error, StaleTemplateVersionError):
        raise HTTPException(
            status_code=HTTPStatus.PRECONDITION_FAILED,
            detail={
                "code": "stale_template_version",
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, TemplateSchemaVersionMismatchError):
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail={
                "code": "template_schema_version_mismatch",
                "schema_version": error.schema_version,
            },
        ) from error
    raise error


@router.post(
    "",
    response_model=ChapterTemplateRead,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("chapter_template.write", "global"))],
)
@inject
def create_chapter_template_endpoint(
    template: ChapterTemplateCreate,
    response: Response,
    service: ChapterTemplatesService = Depends(
        Provide[ApiContainer.services.chapter_templates]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterTemplateRead:
    try:
        read, result = service.create_chapter_template(template, actor)
    except Exception as error:
        _raise_for_template_error(error)
    response.headers["etag"] = result.etag
    return read


@router.get(
    "/{template_id}",
    response_model=ChapterTemplateRead,
    dependencies=[Depends(RequireAuthority("chapter_template.read", "global"))],
)
@inject
def get_chapter_template(
    template_id: UUID,
    service: ChapterTemplatesService = Depends(
        Provide[ApiContainer.services.chapter_templates]
    ),
) -> ChapterTemplateRead:
    try:
        return service.read_chapter_template(template_id)
    except Exception as error:
        _raise_for_template_error(error)


@router.patch(
    "/{template_id}",
    response_model=ChapterTemplateRead,
    dependencies=[Depends(RequireAuthority("chapter_template.write", "global"))],
)
@inject
def patch_chapter_template_endpoint(
    template_id: UUID,
    patch: ChapterTemplatePatch,
    response: Response,
    service: ChapterTemplatesService = Depends(
        Provide[ApiContainer.services.chapter_templates]
    ),
    actor: ActorIdentity = Depends(get_current_actor),
) -> ChapterTemplateRead:
    try:
        read, result = service.patch_chapter_template(template_id, patch, actor)
    except Exception as error:
        _raise_for_template_error(error)
    response.headers["etag"] = result.etag
    return read
