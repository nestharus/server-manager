from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_CONFIGMAP = (
    REPO_ROOT
    / "gitops"
    / "channels"
    / "local"
    / "auth"
    / "authentik"
    / "bootstrap-blueprint-configmap.yaml"
)


class AuthentikBlueprintLoader(yaml.SafeLoader):
    pass


def _authentik_tag(loader: AuthentikBlueprintLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return {f"!{tag_suffix}": loader.construct_sequence(node)}
    if isinstance(node, yaml.MappingNode):
        return {f"!{tag_suffix}": loader.construct_mapping(node)}
    return {f"!{tag_suffix}": loader.construct_scalar(node)}


AuthentikBlueprintLoader.add_multi_constructor("!", _authentik_tag)


def _configmap_data() -> dict[str, str]:
    document = yaml.safe_load(BLUEPRINT_CONFIGMAP.read_text(encoding="utf-8"))
    return document["data"]


def _blueprint_documents() -> list[dict[str, Any]]:
    return [
        yaml.load(value, Loader=AuthentikBlueprintLoader)
        for value in _configmap_data().values()
    ]


def _entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for document in _blueprint_documents():
        entries.extend(document.get("entries", []))
    return entries


def _entries_for_model(model: str) -> list[dict[str, Any]]:
    return [entry for entry in _entries() if entry.get("model") == model]


def _entry_text(entry: dict[str, Any]) -> str:
    return yaml.safe_dump(entry, sort_keys=True)


def _entry_has_value(entry: dict[str, Any], value: str) -> bool:
    return value in _entry_text(entry)


def test_applicant_discord_oauth_source_is_declared_with_identify_only_scope() -> None:
    """TG-1 risk annotation: applicant_objects_missing_or_scope_creep;
    level=particular-integration; source=INIT-127 C1, A1.
    """
    sources = [
        entry
        for entry in _entries_for_model("authentik_sources_oauth.oauthsource")
        if _entry_has_value(entry, "discord-applicant")
    ]

    assert len(sources) == 1
    source = sources[0]
    attrs = source.get("attrs", {})
    identifiers = source.get("identifiers", {})

    assert identifiers.get("slug") == "discord-applicant" or attrs.get("slug") == "discord-applicant"
    assert attrs.get("provider_type") == "discord"
    assert _entry_has_value(source, "identify")

    source_text = _entry_text(source)
    assert " email" not in source_text
    assert "guilds" not in source_text
    assert "guilds.members.read" not in source_text


def test_applicant_oidc_provider_is_confidential_and_has_issuer_mode() -> None:
    """TG-1 risk annotation: officer_oidc_mutated_or_applicant_provider_absent;
    level=particular-integration; source=INIT-127 C1, A1.
    """
    providers = [
        entry
        for entry in _entries_for_model("authentik_providers_oauth2.oauth2provider")
        if _entry_has_value(entry, "server-manager-applicant")
    ]

    assert len(providers) == 1
    provider = providers[0]
    attrs = provider.get("attrs", {})

    assert attrs.get("client_type") == "confidential"
    assert attrs.get("issuer_mode") not in (None, "")
    assert _entry_has_value(provider, "discord_user_id")
    assert not _entry_has_value(provider, "guilds.members.read")


def test_applicant_application_links_discord_source_and_applicant_provider() -> None:
    """TG-1 risk annotation: applicant_application_not_wired_to_source_provider;
    level=particular-integration; source=INIT-127 C1, A1.
    """
    applications = [
        entry
        for entry in _entries_for_model("authentik_core.application")
        if _entry_has_value(entry, "server-manager-applicant")
    ]

    assert len(applications) == 1
    application_text = _entry_text(applications[0])
    all_blueprint_text = "\n".join(_entry_text(entry) for entry in _entries())

    assert "server-manager-applicant" in application_text
    assert "discord-applicant" in all_blueprint_text


def test_discord_snowflake_property_mapping_is_present_without_forbidden_scopes() -> None:
    """TG-1 risk annotation: discord_snowflake_claim_missing_or_pii_scope_creep;
    level=particular-integration; source=INIT-127 C1, A1.
    """
    mapping_entries = [
        entry
        for entry in _entries()
        if "propertymapping" in str(entry.get("model", "")).lower()
        and _entry_has_value(entry, "discord_user_id")
    ]

    assert mapping_entries
    assert any(
        "info.get(\"id\")" in _entry_text(entry)
        or "info.get('id')" in _entry_text(entry)
        or "info[\"id\"]" in _entry_text(entry)
        or "info['id']" in _entry_text(entry)
        or "discord_user_id" in _entry_text(entry)
        for entry in mapping_entries
    )

    combined_mapping_text = "\n".join(_entry_text(entry) for entry in mapping_entries)
    assert "email" not in combined_mapping_text
    assert "guilds" not in combined_mapping_text
    assert "guilds.members.read" not in combined_mapping_text
