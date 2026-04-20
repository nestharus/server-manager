from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ServiceHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["alive"]
    version: str


class DependencyStatusRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: Literal["ok", "degraded", "not_ready"]
    reason: str | None = None


class ServiceReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ready", "not_ready"]
    dependencies: list[DependencyStatusRead]


__all__ = [
    "DependencyStatusRead",
    "ServiceHealthRead",
    "ServiceReadinessRead",
]
