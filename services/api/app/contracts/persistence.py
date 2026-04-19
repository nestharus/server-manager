"""Persistence substrate contracts.

Exposes migration state visibility for operational endpoints. The canonical
data store is Vultr-managed PostgreSQL; Alembic owns schema revisions.
"""

from pydantic import BaseModel


class MigrationRevisionRead(BaseModel):
    """Current Alembic revision applied to the live database."""

    revision: str


__all__ = ["MigrationRevisionRead"]
