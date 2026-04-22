from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.api.v1.endpoints.permissions._shared import get_db, raise_known_permission_error
from app.contracts.actor import ActorIdentity
from app.contracts.read_models import OperationalOverviewRead
from app.core.dependencies import get_current_actor
from app.repositories.db import PostgresDatabase
from app.services.read_models import (
    CursorNotSeededError,
    InvalidScopeError,
    read_operational_overview,
)


router = APIRouter(prefix="/api/v1/operations")


class OperationalOverviewQuery(BaseModel):
    scope_kind: Literal["global", "chapter"]
    scope_id: str | None = None

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def _validate_scope_shape(self) -> "OperationalOverviewQuery":
        if self.scope_kind == "global" and self.scope_id is not None:
            raise ValueError("scope_id must be omitted when scope_kind='global'")
        if self.scope_kind == "chapter" and not self.scope_id:
            raise ValueError("scope_id is required when scope_kind='chapter'")
        return self


def _operational_overview_query(
    scope_kind: Literal["global", "chapter"] = Query(...),
    scope_id: str | None = Query(default=None, min_length=1),
) -> OperationalOverviewQuery:
    try:
        return OperationalOverviewQuery(scope_kind=scope_kind, scope_id=scope_id)
    except ValidationError as error:
        message = error.errors()[0]["msg"]
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": message},
        ) from error


@router.get("/overview", response_model=OperationalOverviewRead)
def get_operational_overview_endpoint(
    query: OperationalOverviewQuery = Depends(_operational_overview_query),
    db: PostgresDatabase = Depends(get_db),
    actor: ActorIdentity = Depends(get_current_actor),
) -> OperationalOverviewRead:
    try:
        return read_operational_overview(
            db,
            scope_kind=query.scope_kind,
            scope_id=query.scope_id,
            actor=actor,
            now=datetime.now(tz=UTC),
        )
    except InvalidScopeError as error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(error)},
        ) from error
    except CursorNotSeededError as error:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail={
                "code": "projection_not_initialized",
                "message": str(error),
            },
        ) from error
    except Exception as error:
        raise_known_permission_error(error)
