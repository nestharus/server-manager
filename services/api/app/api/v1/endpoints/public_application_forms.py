from __future__ import annotations

from fastapi import APIRouter, Depends

from app.contracts.applications import ApplicationScope, FormDefinitionRead
from app.repositories.db import PostgresDatabase
from app.services.forms import get_current_form

from .applications._shared import get_db, raise_known_application_error


router = APIRouter(prefix="/api/v1/public/application-forms")


@router.get("/current", response_model=FormDefinitionRead, response_model_exclude_unset=True)
def get_current_public_application_form_endpoint(
    db: PostgresDatabase = Depends(get_db),
) -> FormDefinitionRead:
    """Public, no auth — returns the current global public application form."""
    try:
        read, _etag = get_current_form(
            db,
            scope=ApplicationScope(scope_kind="global", scope_id=None),
        )
    except Exception as error:
        raise_known_application_error(error)
    return read


__all__ = ["router"]
