from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationScope, FormDefinitionPublish, FormDefinitionRead
from app.core.dependencies import RequireAuthority, get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.forms import get_current_form, publish_form

from ._shared import get_db, parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/application-forms")


@router.post(
    "",
    response_model=FormDefinitionRead,
    response_model_exclude_unset=True,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("application_form.publish", "global"))],
)
def publish_form_endpoint(
    body: FormDefinitionPublish,
    request: Request,
    response: Response,
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> FormDefinitionRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = publish_form(db, body, actor, expected_version)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read


@router.get("/current", response_model=FormDefinitionRead, response_model_exclude_unset=True)
def get_current_form_endpoint(
    scope_kind: str,
    response: Response,
    scope_id: str | None = None,
    db: PostgresDatabase = Depends(get_db),
) -> FormDefinitionRead:
    try:
        read, etag = get_current_form(
            db,
            scope=ApplicationScope(
                scope_kind=scope_kind,  # type: ignore[arg-type]
                scope_id=scope_id,
            ),
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read
