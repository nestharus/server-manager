from pydantic import BaseModel, Field


class VersionedMixin(BaseModel):
    """Mixin for entities supporting optimistic locking.

    Adds a required version field for read/update contracts.
    Exclude from create contracts.
    """

    version: int = Field(ge=0)
