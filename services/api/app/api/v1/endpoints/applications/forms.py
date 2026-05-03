from __future__ import annotations

from http import HTTPStatus

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, Response

from app.contracts.actor import ActorIdentity
from app.contracts.applications import ApplicationScope, FormDefinitionPublish, FormDefinitionRead
from app.core.container import ApiContainer
from app.core.dependencies import RequireAuthority, get_current_actor
from app.services.forms import FormsService

from ._shared import parse_if_match_strong, raise_known_application_error, set_etag


router = APIRouter(prefix="/api/v1/application-forms")


@router.post(
    "",
    response_model=FormDefinitionRead,
    response_model_exclude_unset=True,
    status_code=HTTPStatus.CREATED,
    dependencies=[Depends(RequireAuthority("application_form.publish", "global"))],
)
@inject
def publish_form_endpoint(
    body: FormDefinitionPublish,
    request: Request,
    response: Response,
    service: FormsService = Depends(Provide[ApiContainer.services.forms]),
    actor: ActorIdentity = Depends(get_current_actor),
) -> FormDefinitionRead:
    expected_version = parse_if_match_strong(request)
    try:
        read, result = service.publish_form(body, actor, expected_version)
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, result.etag)
    return read


@router.get("/current", response_model=FormDefinitionRead, response_model_exclude_unset=True)
@inject
def get_current_form_endpoint(
    scope_kind: str,
    response: Response,
    scope_id: str | None = None,
    service: FormsService = Depends(Provide[ApiContainer.services.forms]),
) -> FormDefinitionRead:
    try:
        read, etag = service.get_current_form(
            scope=ApplicationScope(
                scope_kind=scope_kind,  # type: ignore[arg-type]
                scope_id=scope_id,
            ),
        )
    except Exception as error:
        raise_known_application_error(error)
    set_etag(response, etag)
    return read
