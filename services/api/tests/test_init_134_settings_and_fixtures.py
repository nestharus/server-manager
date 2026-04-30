from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.core.settings import Settings

from .public_intake_fixtures import assert_risk_annotation


LIVE_HUMILITY_GUILD_ID = "900000000000000001"
DOCUMENTED_LIVE_DISCORD_IDS = {LIVE_HUMILITY_GUILD_ID}


def _assert_tg4() -> None:
    assert_risk_annotation(
        group="TG-4",
        named_risk="init_134_settings_and_fixture_defense",
        level="component",
        source=".tmp/init-134/phase6/step6a-contract.md#TG-4",
    )


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in (
        "APP_NAME",
        "APP_VERSION",
        "PLATFORM_CHANNEL",
        "PLATFORM_TENANT",
        "DEBUG",
        "API_PREFIX",
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "DISCORD_STAGING_GUILD_ID",
        "SUPABASE_DB_URL",
        "SUPABASE_SERVICE_KEY",
        "GOOGLE_CLOUD_VISION_KEY",
        "GEMINI_API_KEY",
        "Z_AI_API_KEY",
        "MINIMAX_API_KEY",
        "WEB_PUBLIC_BASE_URL",
        "GLOBAL_APPLICATIONS_REVIEW_CHANNEL_ID",
        "GLOBAL_APPLICATION_MANAGERS_ROLE_ID",
        "GLOBAL_PRIMARY_GUILD_CHANNEL_URL",
    ):
        monkeypatch.delenv(env_var, raising=False)


def _set_required_except_web_base(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_env(monkeypatch)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token-value")
    monkeypatch.setenv("DISCORD_GUILD_ID", LIVE_HUMILITY_GUILD_ID)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")


def _fixture_data(repo_root: Path) -> dict[str, Any]:
    path = (
        repo_root
        / "gitops/channels/local/applications/server-manager/"
        "e2e-fixtures-infisicalsecret.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_web_public_base_url_required_no_python_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_tg4()
    _set_required_except_web_base(monkeypatch)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    missing_fields = {str(error["loc"][0]) for error in exc_info.value.errors()}
    assert "web_public_base_url" in missing_fields


def test_e2e_fixture_channel_role_guild_ids_not_live_humility(repo_root: Path) -> None:
    _assert_tg4()
    data = _fixture_data(repo_root)
    template_data = data["spec"]["managedSecretReference"]["template"]["data"]

    expected_fixture_keys = {
        "applicant-discord-user-id",
        "applications-review-channel-id",
        "application-managers-role-id",
        "primary-guild-channel-url",
    }
    assert expected_fixture_keys <= set(template_data)

    fixture_ids = {
        "applicant-discord-user-id": str(template_data["applicant-discord-user-id"]),
        "applications-review-channel-id": str(template_data["applications-review-channel-id"]),
        "application-managers-role-id": str(template_data["application-managers-role-id"]),
    }
    primary_url = str(template_data["primary-guild-channel-url"])
    assert primary_url.startswith("https://discord.com/channels/")
    fixture_ids["primary-guild-channel-url:guild"] = primary_url.split("/")[4]

    for name, value in fixture_ids.items():
        assert value not in DOCUMENTED_LIVE_DISCORD_IDS, (
            f"{name} must use a test-only Discord id, not live Humility"
        )
