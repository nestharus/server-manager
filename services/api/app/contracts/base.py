"""Base contract types.

VersionedMixin implements the optimistic locking pattern from
java-interview-setup: every mutable entity carries a version field.
Updates must include the current version; the repository layer checks
it against the DB row and raises on mismatch.
"""

from __future__ import annotations

import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VersionedMixin(BaseModel):
    """Mixin for entities that support optimistic locking.

    The client receives `version` on reads and must send it back on
    writes. If the DB row's version has changed since the read, the
    write is rejected with a 409 Conflict.
    """

    version: int


class TimestampMixin(BaseModel):
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None


class SoftDeleteMixin(BaseModel):
    archived_at: datetime.datetime | None = None
