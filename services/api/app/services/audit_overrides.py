from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.actor import ActorIdentity
from app.contracts.authority import AuthorityRequirement
from app.contracts.mutations import MutationRequest, StateChangeDraft
from app.core.context import get_current_audit_context
from app.repositories.audit import AuditRepository


class AuditOverridesService:
    def __init__(self, audit_repo: AuditRepository, mutations_callable) -> None:
        self._audit_repo = audit_repo
        self._mutations_callable = mutations_callable

    def record_authority_override(
        self,
        *,
        actor: ActorIdentity,
        requirement: AuthorityRequirement,
        reason: str,
    ) -> None:
        audit_context = get_current_audit_context()
        if audit_context is None:
            raise RuntimeError("missing audit context for authority override")

        timestamp = datetime.now(UTC).isoformat()
        aggregate_id = (
            f"{audit_context.correlation_id}:{requirement.permission}:{timestamp}"
        )
        action_payload = {
            "reason": reason,
            "requirement": requirement.model_dump(mode="json"),
        }

        def mutate_projection(_connection) -> StateChangeDraft:
            return StateChangeDraft(
                change_type="authority_override.recorded",
                payload_json=action_payload,
            )

        self._mutations_callable(
            aggregate_type="authority_override",
            aggregate_id=aggregate_id,
            request=MutationRequest(
                expected_version=0,
                actor_kind=actor.actor_kind,
                actor_id=actor.actor_id,
                reason_text=reason,
                request_surface="dependency:RequireAuthority",
            ),
            action_type="authority.override",
            action_payload=action_payload,
            payload_allowlist={"reason", "requirement"},
            mutate_projection=mutate_projection,
            scope_kind=requirement.scope_kind,
            scope_id=requirement.scope_id,
        )
