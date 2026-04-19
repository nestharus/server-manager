from pydantic import BaseModel, Field


class VersionedMixin(BaseModel):
    """Internal version carrier for optimistic-locking aware models."""

    version: int = Field(ge=0)


__all__ = ["VersionedMixin"]
