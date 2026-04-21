from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.commands.permissions import (
    RECONCILE_PERMISSIONS_COMMAND,
    register_permission_commands,
)
from app.contracts.interactions import InteractionEnvelope
from app.contracts.permissions import (
    DiscordChannelRoleSnapshotEntry,
    DiscordGuildRoleSnapshotEntry,
    DiscordPermissionSnapshotEntry,
    DiscordReconciliationRunRead,
)
from app.handlers.permissions import handle_reconcile_permissions
from app.infrastructure.permission_client import (
    PermissionApiClient,
    PermissionApiConflictError,
    PermissionApiPreconditionFailedError,
)


class Role:
    """Class named 'Role' so handlers' `_is_role` duck check picks it up."""

    def __init__(self, *, id: str, permission_bits: int = 0) -> None:
        self.id = id
        self.permissions = SimpleNamespace(value=permission_bits)


class Member:
    def __init__(self, *, id: str) -> None:
        self.id = id
        self.bot = False


class _Permissions:
    def __init__(self, value: int) -> None:
        self.value = value


class _Overwrite:
    def __init__(self, allow: int, deny: int) -> None:
        self._pair = (_Permissions(allow), _Permissions(deny))

    def pair(self) -> tuple[_Permissions, _Permissions]:
        return self._pair


@dataclass
class FakeChannel:
    id: str
    category: Any = None
    overwrites: dict[Any, _Overwrite] = field(default_factory=dict)


@dataclass
class FakeGuild:
    default_role: Role | None = None
    roles: list[Role] = field(default_factory=list)
    channels: list[FakeChannel] = field(default_factory=list)


class FakePermissionClient:
    def __init__(
        self,
        *,
        create_run: DiscordReconciliationRunRead | Exception,
        submit_result: DiscordReconciliationRunRead | Exception,
    ) -> None:
        self._create_run = create_run
        self._submit_result = submit_result
        self.create_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []

    async def create_reconciliation_run(
        self,
        *,
        scope_kind: str,
        scope_id: str | None,
        originating_actor_kind: str,
        originating_actor_id: str,
    ) -> DiscordReconciliationRunRead:
        self.create_calls.append(
            {
                "scope_kind": scope_kind,
                "scope_id": scope_id,
                "originating_actor_kind": originating_actor_kind,
                "originating_actor_id": originating_actor_id,
            }
        )
        if isinstance(self._create_run, Exception):
            raise self._create_run
        return self._create_run

    async def submit_snapshot(
        self,
        *,
        run_id: UUID,
        entries: list[DiscordPermissionSnapshotEntry],
    ) -> DiscordReconciliationRunRead:
        self.submit_calls.append({"run_id": run_id, "entries": list(entries)})
        if isinstance(self._submit_result, Exception):
            raise self._submit_result
        return self._submit_result


def _envelope(
    *,
    ack: Any | None = None,
    arguments: dict[str, Any] | None = None,
) -> InteractionEnvelope:
    return InteractionEnvelope(
        interaction_id="interaction-1",
        correlation_id=uuid4(),
        actor_kind="discord_user",
        actor_id="1001",
        guild_id="900000000000000001",
        command_name=RECONCILE_PERMISSIONS_COMMAND,
        arguments=arguments or {},
        ack_deferred=ack,
    )


def _run_read(
    *,
    run_id: UUID | None = None,
    status: str = "requested",
    drift_ids: list[UUID] | None = None,
) -> DiscordReconciliationRunRead:
    return DiscordReconciliationRunRead(
        id=run_id or uuid4(),
        scope_kind="global",
        scope_id=None,
        requested_by_kind="user",
        requested_by_id="1001",
        requested_at=datetime.now(UTC),
        status=status,  # type: ignore[arg-type]
        drift_ids=drift_ids or [],
    )


def test_command_registered_under_reconcile_permissions() -> None:
    """AC4: register_permission_commands adds a handler under 'reconcile_permissions'."""
    registered: dict[str, Any] = {}

    class FakeBot:
        permission_client = object()

        def register_interaction_handler(self, name: str, handler: Any) -> Any:
            registered[name] = handler
            return handler

        def get_guild(self, guild_id: int) -> Any:
            return None

    register_permission_commands(FakeBot())
    assert RECONCILE_PERMISSIONS_COMMAND in registered
    assert RECONCILE_PERMISSIONS_COMMAND == "reconcile_permissions"


@pytest.mark.asyncio
async def test_handler_defers_ack_before_api_calls() -> None:
    """AC4: handler calls envelope.ack_deferred before any permission_client call."""
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    run = _run_read()

    class RecordingClient(FakePermissionClient):
        async def create_reconciliation_run(self, **kwargs: Any) -> DiscordReconciliationRunRead:
            events.append("create_run")
            return await super().create_reconciliation_run(**kwargs)

        async def submit_snapshot(self, **kwargs: Any) -> DiscordReconciliationRunRead:
            events.append("submit")
            return await super().submit_snapshot(**kwargs)

    client = RecordingClient(create_run=run, submit_result=_run_read(run_id=run.id, status="reconciled"))
    guild = FakeGuild(roles=[])
    envelope = _envelope(ack=ack)
    await handle_reconcile_permissions(envelope, permission_client=client, guild=guild)
    assert events[0] == "ack"
    assert events.index("ack") < events.index("create_run")


@pytest.mark.asyncio
async def test_global_scope_snapshot_omits_channel_overwrites() -> None:
    """AC4 (D13): global scope snapshot walks guild roles only (no channel walk)."""
    role_a = Role(id="role-a", permission_bits=8)
    role_b = Role(id="role-b", permission_bits=16)
    channel = FakeChannel(
        id="chan-1",
        category=SimpleNamespace(id="category-1"),
        overwrites={role_a: _Overwrite(allow=1, deny=2)},
    )
    guild = FakeGuild(roles=[role_a, role_b], channels=[channel])

    run = _run_read()
    client = FakePermissionClient(
        create_run=run,
        submit_result=_run_read(run_id=run.id, status="reconciled"),
    )
    envelope = _envelope(arguments={})
    await handle_reconcile_permissions(envelope, permission_client=client, guild=guild)

    submitted = client.submit_calls[0]["entries"]
    assert all(isinstance(e, DiscordGuildRoleSnapshotEntry) for e in submitted)
    role_ids = {e.role_id for e in submitted}
    assert role_ids == {"role-a", "role-b"}


@pytest.mark.asyncio
async def test_chapter_scope_snapshot_walks_category_children_and_self() -> None:
    """AC4 (D13): chapter scope walks channels whose category.id matches scope_id."""
    role_a = Role(id="role-a", permission_bits=0)
    category = SimpleNamespace(id="category-42")
    in_scope = FakeChannel(
        id="chan-1",
        category=category,
        overwrites={role_a: _Overwrite(allow=1024, deny=64)},
    )
    scope_self = FakeChannel(
        id="category-42",
        category=None,
        overwrites={role_a: _Overwrite(allow=1, deny=0)},
    )
    out_of_scope = FakeChannel(
        id="chan-2",
        category=SimpleNamespace(id="other-category"),
        overwrites={role_a: _Overwrite(allow=999, deny=999)},
    )
    guild = FakeGuild(
        roles=[role_a],
        channels=[in_scope, scope_self, out_of_scope],
    )

    run = _run_read()
    client = FakePermissionClient(
        create_run=run,
        submit_result=_run_read(run_id=run.id, status="reconciled"),
    )
    envelope = _envelope(arguments={"chapter": "category-42"})
    await handle_reconcile_permissions(envelope, permission_client=client, guild=guild)

    assert client.create_calls[0]["scope_kind"] == "chapter"
    assert client.create_calls[0]["scope_id"] == "category-42"

    channel_entries = [
        e
        for e in client.submit_calls[0]["entries"]
        if isinstance(e, DiscordChannelRoleSnapshotEntry)
    ]
    walked_channels = {e.channel_id for e in channel_entries}
    assert walked_channels == {"chan-1", "category-42"}


@pytest.mark.asyncio
async def test_snapshot_skips_default_role() -> None:
    """AC4 (D13): @everyone (guild.default_role) is excluded from the snapshot."""
    default = Role(id="everyone", permission_bits=0)
    role = Role(id="role-a", permission_bits=8)
    guild = FakeGuild(default_role=default, roles=[default, role])

    run = _run_read()
    client = FakePermissionClient(
        create_run=run,
        submit_result=_run_read(run_id=run.id, status="reconciled"),
    )
    await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=guild,
    )
    role_ids = {e.role_id for e in client.submit_calls[0]["entries"]}
    assert role_ids == {"role-a"}


@pytest.mark.asyncio
async def test_channel_overwrites_skip_default_role() -> None:
    """CodeRabbit MAJOR 3: @everyone overwrites must be filtered from the
    channel snapshot the same way guild-role entries skip guild.default_role,
    otherwise every channel with an @everyone overwrite creates persistent
    drift noise."""
    default = Role(id="everyone", permission_bits=0)
    role = Role(id="role-a", permission_bits=0)
    channel = FakeChannel(
        id="chan-1",
        category=SimpleNamespace(id="cat-1"),
        overwrites={
            default: _Overwrite(allow=1024, deny=0),
            role: _Overwrite(allow=64, deny=0),
        },
    )
    guild = FakeGuild(
        default_role=default,
        roles=[default, role],
        channels=[channel],
    )

    run = _run_read()
    client = FakePermissionClient(
        create_run=run,
        submit_result=_run_read(run_id=run.id, status="reconciled"),
    )
    envelope = _envelope(arguments={"chapter": "cat-1"})
    await handle_reconcile_permissions(
        envelope, permission_client=client, guild=guild,
    )

    channel_entries = [
        e
        for e in client.submit_calls[0]["entries"]
        if isinstance(e, DiscordChannelRoleSnapshotEntry)
    ]
    role_ids = {e.role_id for e in channel_entries}
    assert role_ids == {"role-a"}
    assert "everyone" not in role_ids


@pytest.mark.asyncio
async def test_snapshot_formats_bits_as_decimal_strings() -> None:
    """AC4: permission bits are emitted as decimal strings matching DecimalBitString."""
    role = Role(id="role-x", permission_bits=2147483648)  # > 32-bit signed
    channel = FakeChannel(
        id="chan-1",
        category=SimpleNamespace(id="cat-1"),
        overwrites={role: _Overwrite(allow=9007199254740992, deny=0)},
    )
    guild = FakeGuild(roles=[role], channels=[channel])

    run = _run_read()
    client = FakePermissionClient(
        create_run=run,
        submit_result=_run_read(run_id=run.id, status="reconciled"),
    )
    envelope = _envelope(arguments={"chapter": "cat-1"})
    await handle_reconcile_permissions(envelope, permission_client=client, guild=guild)

    guild_entry = next(
        e
        for e in client.submit_calls[0]["entries"]
        if isinstance(e, DiscordGuildRoleSnapshotEntry)
    )
    channel_entry = next(
        e
        for e in client.submit_calls[0]["entries"]
        if isinstance(e, DiscordChannelRoleSnapshotEntry)
    )
    assert guild_entry.permission_bits == "2147483648"
    assert channel_entry.allow_bits == "9007199254740992"
    assert channel_entry.deny_bits == "0"


@pytest.mark.asyncio
async def test_handler_returns_ephemeral_error_when_guild_missing() -> None:
    """AC4: when guild is None the handler returns an ephemeral error without calling the API."""
    client = FakePermissionClient(
        create_run=_run_read(),
        submit_result=_run_read(),
    )
    result = await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=None,
    )
    assert result.success is False
    assert result.ephemeral is True
    assert client.create_calls == []
    assert client.submit_calls == []


@pytest.mark.asyncio
async def test_handler_returns_ephemeral_error_on_precondition_failed() -> None:
    """AC4: 412 from submit_snapshot surfaces as an ephemeral retry message."""
    run = _run_read()
    precondition_error = PermissionApiPreconditionFailedError(
        status=412, reason="stale version", body={"code": "stale_permission_version"},
    )
    client = FakePermissionClient(
        create_run=run,
        submit_result=precondition_error,
    )
    guild = FakeGuild(roles=[Role(id="role-a")])
    result = await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=guild,
    )
    assert result.success is False
    assert "concurrent" in (result.response_text or "").lower()


@pytest.mark.asyncio
async def test_handler_returns_ephemeral_error_when_previous_run_failed_on_conflict() -> None:
    """AC4: 409 with status='failed' surfaces as 'retry with a new run'."""
    run = _run_read()
    conflict_error = PermissionApiConflictError(
        status=409,
        reason="run in failed state",
        body={
            "code": "reconciliation_run_conflict",
            "status": "failed",
            "message": "run in status failed",
        },
    )
    client = FakePermissionClient(
        create_run=run,
        submit_result=conflict_error,
    )
    guild = FakeGuild(roles=[Role(id="role-a")])
    result = await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=guild,
    )
    assert result.success is False
    assert "failed" in (result.response_text or "").lower()
    assert "retry" in (result.response_text or "").lower()


@pytest.mark.asyncio
async def test_handler_reports_non_terminal_409_as_error() -> None:
    """CodeRabbit CRITICAL 2: a 409 with non-terminal status (e.g.
    'snapshot_submitted' from a concurrent submit) must NOT be silently
    treated as success — it must surface as an ephemeral error."""
    run = _run_read()
    conflict_error = PermissionApiConflictError(
        status=409,
        reason="run in snapshot_submitted state",
        body={
            "code": "reconciliation_run_conflict",
            "status": "snapshot_submitted",
            "message": "run in status snapshot_submitted",
        },
    )
    client = FakePermissionClient(
        create_run=run,
        submit_result=conflict_error,
    )
    guild = FakeGuild(roles=[Role(id="role-a")])
    result = await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=guild,
    )
    assert result.success is False
    text = (result.response_text or "").lower()
    assert "conflict" in text
    assert "snapshot_submitted" in text


@pytest.mark.asyncio
async def test_handler_treats_reconciled_409_as_idempotent_success() -> None:
    """CodeRabbit CRITICAL 2: a 409 with status='reconciled' is an idempotent
    terminal replay and should be reported as success."""
    run = _run_read()
    conflict_error = PermissionApiConflictError(
        status=409,
        reason="run already reconciled",
        body={
            "code": "reconciliation_run_conflict",
            "status": "reconciled",
            "message": "run in status reconciled",
        },
    )
    client = FakePermissionClient(
        create_run=run,
        submit_result=conflict_error,
    )
    guild = FakeGuild(roles=[Role(id="role-a")])
    result = await handle_reconcile_permissions(
        _envelope(), permission_client=client, guild=guild,
    )
    assert result.success is True
