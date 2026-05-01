from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts.applications import ApplicationFormField, FormDefinitionPublish


def _publish_payload(fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": "Global File Field Contract",
        "target_type": "chapter_membership",
        "scope": {"scope_kind": "global", "scope_id": None},
        "fields": fields,
        "routing_rules": {
            "schema_version": 1,
            "queue": "chapter_officers",
            "review_scope": {"scope_kind": "global", "scope_id": None},
        },
    }


def _base_file_field(**overrides: Any) -> dict[str, Any]:
    field: dict[str, Any] = {
        "id": "character_sheet",
        "type": "file",
        "label": "Character sheet",
        "required": True,
        "accept": ["image/png", "application/pdf"],
        "max_size_bytes": 1_048_576,
        "page": 2,
    }
    field.update(overrides)
    return field


def _source_field() -> dict[str, Any]:
    return {
        "id": "has_character_sheet",
        "type": "boolean",
        "label": "Has character sheet",
        "required": True,
        "page": 1,
    }


def test_application_form_field_union_accepts_file_with_page_and_visible_when() -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    adapter = TypeAdapter(ApplicationFormField)

    parsed = adapter.validate_python(
        _base_file_field(
            visible_when={
                "field_id": "has_character_sheet",
                "op": "eq",
                "value": True,
            },
        )
    )

    assert parsed.type == "file"
    assert parsed.accept == ["image/png", "application/pdf"]
    assert parsed.max_size_bytes == 1_048_576
    assert parsed.page == 2
    assert parsed.visible_when is not None
    assert parsed.visible_when.field_id == "has_character_sheet"


@pytest.mark.parametrize(
    "accept",
    [
        pytest.param([], id="empty"),
        pytest.param(["pdf"], id="bare-subtype"),
        pytest.param(["application"], id="missing-subtype"),
        pytest.param(["image/"], id="empty-subtype"),
        pytest.param(["/png"], id="empty-type"),
        pytest.param(["image/*"], id="subtype-wildcard"),
        pytest.param(["*/*"], id="full-wildcard"),
        pytest.param(["image/png", "image/png"], id="duplicate"),
    ],
)
def test_publish_form_rejects_invalid_file_accept_allowlist(
    accept: list[str],
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1-F1.
    """
    with pytest.raises(ValidationError):
        FormDefinitionPublish.model_validate(
            _publish_payload([_base_file_field(accept=accept)])
        )


@pytest.mark.parametrize(
    "max_size_bytes",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(100 * 1024 * 1024 + 1, id="above-100-mib-cap"),
    ],
)
def test_publish_form_rejects_invalid_file_max_size_bytes(
    max_size_bytes: int,
) -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    with pytest.raises(ValidationError):
        FormDefinitionPublish.model_validate(
            _publish_payload([_base_file_field(max_size_bytes=max_size_bytes)])
        )


def test_publish_form_rejects_two_file_fields() -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1-F3.
    """
    with pytest.raises(ValidationError):
        FormDefinitionPublish.model_validate(
            _publish_payload(
                [
                    _base_file_field(id="character_sheet"),
                    _base_file_field(id="screenshot", label="Screenshot"),
                ]
            )
        )


def test_publish_form_accepts_file_field_visible_when() -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    parsed = FormDefinitionPublish.model_validate(
        _publish_payload(
            [
                _source_field(),
                _base_file_field(
                    visible_when={
                        "field_id": "has_character_sheet",
                        "op": "eq",
                        "value": True,
                    }
                ),
            ]
        )
    )

    file_field = parsed.fields[1]
    assert file_field.type == "file"
    assert file_field.visible_when is not None
    assert file_field.visible_when.field_id == "has_character_sheet"


def test_publish_form_rejects_file_field_as_visible_when_source() -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    with pytest.raises(ValidationError):
        FormDefinitionPublish.model_validate(
            _publish_payload(
                [
                    _base_file_field(required=False),
                    {
                        "id": "sheet_notes",
                        "type": "long",
                        "label": "Sheet notes",
                        "required": False,
                        "max_length": 4000,
                        "visible_when": {
                            "field_id": "character_sheet",
                            "op": "eq",
                            "value": "uploaded",
                        },
                    },
                ]
            )
        )


def test_application_form_field_union_still_accepts_all_existing_variants() -> None:
    """Risk annotation: group=TG-1;
    named_risk=file_field_contract_roundtrip_and_publish_validators;
    level=contract;
    source=.tmp/init-137-file-upload/phase6/step6a-contract.md#TG-1.
    """
    adapter = TypeAdapter(ApplicationFormField)
    raw_fields: list[dict[str, Any]] = [
        {"id": "short_answer", "type": "short", "label": "Short", "max_length": 64},
        {"id": "long_answer", "type": "long", "label": "Long", "max_length": 4000},
        {"id": "raid_count", "type": "number", "label": "Raid count"},
        {
            "id": "class",
            "type": "select",
            "label": "Class",
            "options": ["warrior", "mage"],
        },
        {
            "id": "roles",
            "type": "multi_select",
            "label": "Roles",
            "options": ["tank", "healer"],
        },
        {"id": "rules", "type": "boolean", "label": "Rules accepted"},
        {
            "id": "chapter",
            "type": "chapter_select",
            "label": "Chapter",
            "required": True,
        },
    ]

    parsed = [adapter.validate_python(field) for field in raw_fields]

    assert [field.type for field in parsed] == [
        "short",
        "long",
        "number",
        "select",
        "multi_select",
        "boolean",
        "chapter_select",
    ]
