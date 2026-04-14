from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class BaseContract(BaseModel):
    """Base class for all API contracts.

    Enables from_attributes so contracts can be validated from
    dataclass/ORM instances.
    """

    model_config = ConfigDict(from_attributes=True)


class VersionedMixin(BaseModel):
    """Mixin for entities supporting optimistic locking.

    Adds a required version field for read/update contracts.
    Exclude from create contracts.
    """

    version: int = Field(ge=0)


class TimestampMixin(BaseModel):
    """Mixin for entities with server-managed timestamps."""

    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None


class SoftDeleteMixin(BaseModel):
    """Mixin for entities supporting soft deletion."""

    archived_at: datetime.datetime | None = None
