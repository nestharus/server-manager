from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.contracts.api_transport import ApiUnreachableError


class DiscordRuntimeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["stopped", "failed"]
    api_base_url: str
    started_at: datetime
    missing_dependency: str | None = None


class DiscordLoginError(Exception):
    def __init__(self, *, reason: str, missing_dependency: str = "discord_login") -> None:
        self.reason = reason
        self.missing_dependency = missing_dependency
        super().__init__(reason)


class CommandSyncError(Exception):
    def __init__(self, *, reason: str, missing_dependency: str = "command_tree_sync") -> None:
        self.reason = reason
        self.missing_dependency = missing_dependency
        super().__init__(reason)


__all__ = [
    "ApiUnreachableError",
    "CommandSyncError",
    "DiscordLoginError",
    "DiscordRuntimeRead",
]
