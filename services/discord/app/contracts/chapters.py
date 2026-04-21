from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


ProvisioningStep = Literal[
    "ack",
    "fetch_chapter",
    "transition_provisioning",
    "category",
    "role",
    "channel",
    "api_confirm",
    "transition_active",
    "transition_failed",
]


class ChapterProvisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chapter_id: str
    success: bool
    failed_step: ProvisioningStep | None = None
    message: str


class ChapterProvisioningError(Exception):
    def __init__(self, *, step: ProvisioningStep, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"{step}: {reason}")


__all__ = [
    "ChapterProvisionResult",
    "ChapterProvisioningError",
    "ProvisioningStep",
]
