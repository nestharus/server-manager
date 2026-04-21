from __future__ import annotations

from typing import Any
from uuid import UUID

from app.contracts.api_transport import (
    ApiTransportError,
    ApiTransportRequest,
    ApiTransportResponse,
    ApiUnreachableError,
)
from app.contracts.application_interview import ApplicationInterviewCommand
from app.contracts.interactions import InteractionEnvelope, InteractionResult
from app.handlers.application_submission import build_user_actor_headers, resolve_member_id


_INTERVIEW_NAME_LEN = 12


async def _api_call(api_client: Any, request: ApiTransportRequest) -> ApiTransportResponse:
    return await api_client.call(request)


def _etag(response: ApiTransportResponse) -> str:
    for key, value in response.headers.items():
        if key.lower() == "etag":
            return value
    raise RuntimeError("API response missing ETag")


def _iter(values: Any) -> tuple[Any, ...]:
    if values is None:
        return ()
    return tuple(values)


def _interview_thread_name(application_id: str) -> str:
    return f"interview-{UUID(str(application_id)).hex[:_INTERVIEW_NAME_LEN]}"


def _application_marker(application_id: str) -> str:
    return f"application_id={application_id}"


def _thread_id(thread: Any) -> str | None:
    value = getattr(thread, "id", None)
    if value is None:
        return None
    return str(value)


def _candidate_threads(guild: Any) -> tuple[Any, ...]:
    threads = list(_iter(getattr(guild, "threads", None)))
    channels = list(_iter(getattr(guild, "channels", None)))
    review_channel = getattr(guild, "application_review_channel", None)
    if review_channel is not None:
        threads.extend(_iter(getattr(review_channel, "threads", None)))
    return tuple(threads + channels)


def _find_thread_by_id(guild: Any, thread_id: str) -> Any | None:
    for thread in _candidate_threads(guild):
        if _thread_id(thread) == str(thread_id):
            return thread
    return None


def _find_thread_by_application(guild: Any, application_id: str) -> Any | None:
    name = _interview_thread_name(application_id)
    marker = _application_marker(application_id)
    for thread in _candidate_threads(guild):
        if getattr(thread, "name", None) == name:
            return thread
        topic = getattr(thread, "topic", None)
        if isinstance(topic, str) and marker in topic:
            return thread
        stored_marker = getattr(thread, "application_marker", None)
        if stored_marker == marker:
            return thread
    return None


async def _call_create_thread(target: Any, *, name: str, marker: str) -> Any:
    try:
        return await target.create_thread(name=name, reason=marker)
    except TypeError:
        return await target.create_thread(name=name)


async def _create_interview_thread(guild: Any, *, application_id: str) -> Any:
    name = _interview_thread_name(application_id)
    marker = _application_marker(application_id)
    parent = getattr(guild, "application_review_channel", None)
    if parent is not None and hasattr(parent, "create_thread"):
        thread = await _call_create_thread(parent, name=name, marker=marker)
    elif hasattr(guild, "create_thread"):
        thread = await _call_create_thread(guild, name=name, marker=marker)
    elif hasattr(guild, "create_text_channel"):
        thread = await guild.create_text_channel(name, topic=marker)
    else:
        raise RuntimeError("guild cannot create an interview thread")

    if hasattr(thread, "send"):
        await thread.send(content=marker)
    if not hasattr(thread, "application_marker"):
        try:
            thread.application_marker = marker
        except Exception:
            pass
    return thread


async def _resolve_or_create_interview_thread(
    guild: Any,
    *,
    application_id: str,
    stored_thread_id: str | None,
) -> str:
    if stored_thread_id:
        existing = _find_thread_by_id(guild, stored_thread_id)
        if existing is not None:
            return str(stored_thread_id)
        discovered = _find_thread_by_application(guild, application_id)
        if discovered is not None and _thread_id(discovered) == str(stored_thread_id):
            return str(stored_thread_id)
        return str(stored_thread_id)

    discovered = _find_thread_by_application(guild, application_id)
    if discovered is not None and _thread_id(discovered) is not None:
        return str(_thread_id(discovered))

    thread = await _create_interview_thread(guild, application_id=application_id)
    thread_id = _thread_id(thread)
    if thread_id is None:
        raise RuntimeError("created interview thread did not expose an id")
    return thread_id


async def handle_application_interview(
    envelope: InteractionEnvelope,
    *,
    api_client: Any | None = None,
    guild: Any | None = None,
) -> InteractionResult:
    if envelope.ack_deferred is not None:
        await envelope.ack_deferred()

    if api_client is None or guild is None:
        return InteractionResult(success=False, response_text="Application interview is not configured.")

    command = ApplicationInterviewCommand.model_validate(envelope.arguments)
    try:
        member_id = await resolve_member_id(api_client, envelope.actor_id)
        headers = build_user_actor_headers(member_id)
        current = await _api_call(
            api_client,
            ApiTransportRequest(
                method="GET",
                path=f"/api/v1/applications/{command.application_id}",
                headers=headers,
            ),
        )
        if current.status >= 400 or current.body is None:
            return InteractionResult(success=False, response_text="Application interview failed.")
        thread_id = await _resolve_or_create_interview_thread(
            guild,
            application_id=command.application_id,
            stored_thread_id=current.body.get("interview_thread_id"),
        )
        response = await _api_call(
            api_client,
            ApiTransportRequest(
                method="POST",
                path=f"/api/v1/applications/{command.application_id}/interview",
                body={
                    "thread_id": thread_id,
                    "reason": command.reason,
                    "originating_actor_kind": "user",
                    "originating_actor_id": member_id,
                },
                headers={**headers, "If-Match": _etag(current)},
            ),
        )
    except (ApiTransportError, ApiUnreachableError, RuntimeError):
        return InteractionResult(success=False, response_text="Application interview failed.")

    payload = response.body or {}
    if response.status == 409 and payload.get("code") == "application_interview_thread_mismatch":
        return InteractionResult(
            success=False,
            response_text="Application already has a different interview thread.",
        )
    if response.status == 412:
        return InteractionResult(
            success=False,
            response_text="Application changed. Retry the interview request.",
        )
    if response.status >= 400:
        return InteractionResult(success=False, response_text="Application interview failed.")

    return InteractionResult(
        success=True,
        response_text=f"Application {payload['id']} interview thread ready.",
    )


__all__ = [
    "_application_marker",
    "_interview_thread_name",
    "handle_application_interview",
]
