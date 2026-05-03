from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.contracts.applications import ApplicationScope, FormDefinitionRead
from app.core.container import ApiContainer
from app.services.forms import FormsService

from .applications._shared import raise_known_application_error


router = APIRouter(prefix="/api/v1/public/application-forms")


@router.get("/current", response_model=FormDefinitionRead, response_model_exclude_unset=True)
@inject
def get_current_public_application_form_endpoint(
    service: FormsService = Depends(Provide[ApiContainer.services.forms]),
) -> FormDefinitionRead:
    """Public, no auth — returns the current global public application form."""
    try:
        read, _etag = service.get_current_form(
            scope=ApplicationScope(scope_kind="global", scope_id=None),
        )
    except Exception as error:
        raise_known_application_error(error)
    return read


__all__ = ["router"]
