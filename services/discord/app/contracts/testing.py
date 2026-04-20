from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict


class DiscordTestHarnessRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bot_fixture_name: Literal["bot"]
    interaction_factory_fixture_name: Literal["interaction_factory"]
    api_client_stub_fixture_name: Literal["api_client_stub"]


DISCORD_TEST_HARNESS: Final[DiscordTestHarnessRead] = DiscordTestHarnessRead(
    bot_fixture_name="bot",
    interaction_factory_fixture_name="interaction_factory",
    api_client_stub_fixture_name="api_client_stub",
)
