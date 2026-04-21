from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


class MockDiscordHTTPException(Exception):
    pass


@dataclass(frozen=True)
class MockRole:
    id: int
    name: str


@dataclass(frozen=True)
class MockCategory:
    id: int
    name: str


@dataclass(frozen=True)
class MockPermissionOverwrite:
    view_channel: bool
    send_messages: bool


@dataclass
class MockTextChannel:
    id: int
    name: str
    category: MockCategory
    overwrites: dict[MockRole, MockPermissionOverwrite]


@dataclass
class ProvisioningResult:
    ok: bool
    created_resources: list[dict[str, Any]]
    cleanup_required: list[dict[str, Any]]
    error: str | None = None


@dataclass
class MockGuild:
    fail_on: dict[str, set[int]] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)
    created_roles: list[MockRole] = field(default_factory=list)
    created_categories: list[MockCategory] = field(default_factory=list)
    created_text_channels: list[MockTextChannel] = field(default_factory=list)
    _next_id: int = 960000

    def _next_call(self, method_name: str) -> int:
        call_number = self.calls.get(method_name, 0) + 1
        self.calls[method_name] = call_number
        if call_number in self.fail_on.get(method_name, set()):
            raise MockDiscordHTTPException(
                f"injected {method_name} failure on call {call_number}"
            )
        return call_number

    def _allocate_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def create_category(self, name: str, *, reason: str) -> MockCategory:
        self._next_call("create_category")
        category = MockCategory(id=self._allocate_id(), name=name)
        self.created_categories.append(category)
        return category

    async def create_role(self, *, name: str, reason: str) -> MockRole:
        self._next_call("create_role")
        role = MockRole(id=self._allocate_id(), name=name)
        self.created_roles.append(role)
        return role

    async def create_text_channel(
        self,
        name: str,
        *,
        category: MockCategory,
        overwrites: dict[MockRole, MockPermissionOverwrite],
        reason: str,
    ) -> MockTextChannel:
        self._next_call("create_text_channel")
        channel = MockTextChannel(
            id=self._allocate_id(),
            name=name,
            category=category,
            overwrites=overwrites,
        )
        self.created_text_channels.append(channel)
        return channel


async def provision_chapter(guild: MockGuild, chapter_slug: str) -> ProvisioningResult:
    created: list[dict[str, Any]] = []

    try:
        category = await guild.create_category(
            f"{chapter_slug}-chapter",
            reason=f"provision chapter {chapter_slug}",
        )
        created.append({"kind": "category", "id": category.id, "name": category.name})

        officer_role = await guild.create_role(
            name=f"{chapter_slug}-officer",
            reason=f"provision chapter {chapter_slug}",
        )
        created.append(
            {"kind": "role", "id": officer_role.id, "name": officer_role.name}
        )

        member_role = await guild.create_role(
            name=f"{chapter_slug}-member",
            reason=f"provision chapter {chapter_slug}",
        )
        created.append({"kind": "role", "id": member_role.id, "name": member_role.name})

        overwrites = {
            officer_role: MockPermissionOverwrite(
                view_channel=True,
                send_messages=True,
            ),
            member_role: MockPermissionOverwrite(
                view_channel=True,
                send_messages=False,
            ),
        }
        channel = await guild.create_text_channel(
            "announcements",
            category=category,
            overwrites=overwrites,
            reason=f"provision chapter {chapter_slug}",
        )
        created.append(
            {"kind": "text_channel", "id": channel.id, "name": channel.name}
        )

        return ProvisioningResult(ok=True, created_resources=created, cleanup_required=[])
    except MockDiscordHTTPException as error:
        cleanup_required = [
            resource
            for resource in created
            if resource["kind"] in {"role", "category", "text_channel"}
        ]
        return ProvisioningResult(
            ok=False,
            created_resources=created,
            cleanup_required=cleanup_required,
            error=str(error),
        )


def _print_successful_flow(result: ProvisioningResult, guild: MockGuild) -> None:
    print("SUCCESSFUL FLOW")
    print(f"ok={result.ok}")
    print(f"created_resources={result.created_resources}")
    channel = guild.created_text_channels[0]
    print("text channel overwrites:")
    for role, overwrite in channel.overwrites.items():
        print(
            f"  role={role.name} role_id={role.id} "
            f"view={overwrite.view_channel} send={overwrite.send_messages}"
        )


def _print_partial_failure(result: ProvisioningResult) -> None:
    print("\nPARTIAL FAILURE FLOW")
    print(f"ok={result.ok}")
    print(f"error={result.error}")
    print(f"created_before_failure={result.created_resources}")
    print(f"cleanup_required={result.cleanup_required}")
    first_role = next(
        resource for resource in result.cleanup_required if resource["kind"] == "role"
    )
    print(f"recorded first role id for later cleanup: {first_role['id']}")


async def main() -> None:
    successful_guild = MockGuild()
    success = await provision_chapter(successful_guild, "alpha")
    _print_successful_flow(success, successful_guild)

    failing_guild = MockGuild(fail_on={"create_role": {2}})
    failed = await provision_chapter(failing_guild, "bravo")
    _print_partial_failure(failed)


if __name__ == "__main__":
    asyncio.run(main())
