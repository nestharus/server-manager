from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChannelSpec(BaseModel):
    name: str
    type: str
    topic: str | None = None


class RoleSpec(BaseModel):
    name: str
    ordinal: int
    triggers_succession: bool = False


class DefaultPermissionIntent(BaseModel):
    role_name: str
    kind: str
    channel_name: str | None = None
    allow_bits: str | None = None
    deny_bits: str | None = None
    permission_bits: str | None = None


class ChapterTemplate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    channel_structure: list[ChannelSpec]
    role_structure: list[RoleSpec]
    default_permission_intents: list[DefaultPermissionIntent]


class Chapter(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    template_id: UUID
    configuration: dict[str, Any]


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def provision_from_template(template: ChapterTemplate, chapter_name: str) -> Chapter:
    snapshot = deepcopy(
        {
            "template_name": template.name,
            "channel_structure": [
                model_to_dict(channel) for channel in template.channel_structure
            ],
            "role_structure": [model_to_dict(role) for role in template.role_structure],
            "default_permission_intents": [
                model_to_dict(intent)
                for intent in template.default_permission_intents
            ],
        }
    )
    return Chapter(
        name=chapter_name,
        template_id=template.id,
        configuration=snapshot,
    )


def edited_template(template: ChapterTemplate) -> ChapterTemplate:
    update = {
        "name": "Chapter Template v2",
        "channel_structure": [
            *template.channel_structure,
            ChannelSpec(name="after-action-reports", type="text"),
        ],
        "role_structure": [
            *template.role_structure,
            RoleSpec(name="Logistics", ordinal=2),
        ],
    }
    if hasattr(template, "model_copy"):
        return template.model_copy(update=update)
    return template.copy(update=update)


def main() -> None:
    template = ChapterTemplate(
        name="Chapter Template v1",
        channel_structure=[
            ChannelSpec(name="announcements", type="text"),
            ChannelSpec(name="operations", type="text", topic="Chapter operations"),
        ],
        role_structure=[
            RoleSpec(name="Officer", ordinal=0, triggers_succession=True),
            RoleSpec(name="Member", ordinal=1),
        ],
        default_permission_intents=[
            DefaultPermissionIntent(
                role_name="Officer",
                kind="channel_role",
                channel_name="operations",
                allow_bits="1024",
                deny_bits="0",
            )
        ],
    )

    chapter = provision_from_template(template, "Alpha Chapter")
    changed_template = edited_template(template)

    print("TEMPLATE AT PROVISION TIME")
    print(model_to_dict(template))
    print("\nCHAPTER SNAPSHOT")
    print(model_to_dict(chapter))
    print("\nTEMPLATE AFTER LATER EDIT")
    print(model_to_dict(changed_template))
    print("\nCOPY-ON-INSTANTIATE CHECK")
    print(
        "chapter channel count remains "
        f"{len(chapter.configuration['channel_structure'])}; "
        "edited template channel count is "
        f"{len(changed_template.channel_structure)}"
    )
    print(f"provenance template_id retained: {chapter.template_id}")


if __name__ == "__main__":
    main()
