from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicChapterSummaryRead(_PublicModel):
    id: str
    name: str


class PublicChapterListRead(_PublicModel):
    chapters: list[PublicChapterSummaryRead]


__all__ = [
    "PublicChapterListRead",
    "PublicChapterSummaryRead",
]
