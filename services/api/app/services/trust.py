from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.members import MemberNotFoundError
from app.contracts.mutations import MutationRequest, MutationResult, StaleMutationError, StateChangeDraft
from app.contracts.trust import (
    InvalidTrustPolicyError,
    InvalidTrustSignalActorError,
    InvalidTrustSignalScopeError,
    NoTrustPolicyConfiguredError,
    TrustProfileNotFoundError,
    TrustProfileRead,
    TrustRecomputeConflictError,
    TrustSignalCreate,
    TrustSignalRead,
    TrustSignalScope,
    TrustSignalsInput,
)
from app.repositories.members import MembersRepository
from app.repositories.policies import PoliciesRepository
from app.repositories.trust import TrustRepository
from app.services.members import is_synthetic_member


TRUST_POLICY_TYPE = "trust_computation"
TRUST_PROFILE_AGGREGATE_TYPE = "trust_profile"
TRUST_SIGNAL_AGGREGATE_TYPE = "trust_signal"
TRUST_SIGNAL_CREATE_ACTION = "trust.signal.created"
TRUST_SIGNAL_CREATE_CHANGE = "trust.signal.created"
TRUST_RECOMPUTE_ACTION = "trust.recompute"
TRUST_RECOMPUTE_CHANGE = "trust.recomputed"


@dataclass(frozen=True, slots=True)
class ComputedTrust:
    score: int
    tier: str
    summary: dict[str, Any]


def _make_request(
    *,
    expected_version: int,
    actor: ActorIdentity,
    request_surface: str,
) -> MutationRequest:
    return MutationRequest(
        expected_version=expected_version,
        actor_kind=actor.actor_kind,
        actor_id=actor.actor_id,
        reason_text=None,
        request_surface=request_surface,
    )


def _profile_from_row(row: dict[str, Any]) -> TrustProfileRead:
    return TrustProfileRead(
        member_id=row["member_id"],
        score=int(row["score"]),
        tier=row["tier"],
        signals=dict(row["signals"]),
        policy_version_id=row["policy_version_id"],
        config_version=int(row["config_version"]),
        version=int(row["version"]),
    )


def _signal_from_row(row: dict[str, Any]) -> TrustSignalRead:
    return TrustSignalRead(
        id=row["id"],
        member_id=row["member_id"],
        signal_type=row["signal_type"],
        scope=TrustSignalScope(scope_kind=row["scope_kind"], scope_id=row["scope_id"]),
        value=dict(row["value"]),
        source_actor_kind=row["source_actor_kind"],
        source_actor_id=row["source_actor_id"],
        observed_at=row["observed_at"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
    )


def _fetch_profile_row(
    trust_repo: TrustRepository,
    connection: Connection[Any],
    member_id: UUID,
) -> dict[str, Any]:
    row = trust_repo._fetch_trust_profile_by_member_id_on(connection, member_id)
    if row is None:
        raise TrustProfileNotFoundError(member_id)
    return row


def _raise_synthetic_trust_subject() -> None:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={
            "code": "trust_subject_synthetic_not_allowed",
            "message": "Synthetic public-intake members cannot have trust signals.",
        },
    )


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidTrustPolicyError(f"{path} must be an object")
    return value


def _as_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTrustPolicyError(f"{path} must be numeric")
    return float(value)


def _policy_config(policy_content: Mapping[str, Any]) -> dict[str, Any]:
    schema_version = policy_content.get("schema_version")
    if schema_version != 1:
        raise InvalidTrustPolicyError("policy.content.schema_version must be 1")

    floor = _as_number(policy_content.get("score_floor"), "policy.content.score_floor")
    ceiling = _as_number(policy_content.get("score_ceiling"), "policy.content.score_ceiling")
    default = _as_number(policy_content.get("default_score"), "policy.content.default_score")
    if floor > ceiling:
        raise InvalidTrustPolicyError("policy.content.score_floor must be <= score_ceiling")

    signal_weights = _as_mapping(policy_content.get("signal_weights"), "policy.content.signal_weights")
    decay_rules = _as_mapping(policy_content.get("decay_rules"), "policy.content.decay_rules")
    if decay_rules:
        raise InvalidTrustPolicyError("decay_rules not yet supported")
    thresholds = policy_content.get("level_thresholds")
    if not isinstance(thresholds, Sequence) or isinstance(thresholds, (str, bytes)):
        raise InvalidTrustPolicyError("policy.content.level_thresholds must be an array")
    if not thresholds:
        raise InvalidTrustPolicyError("policy.content.level_thresholds must not be empty")

    parsed_thresholds: list[dict[str, Any]] = []
    for index, threshold_raw in enumerate(thresholds):
        threshold = _as_mapping(threshold_raw, f"policy.content.level_thresholds.{index}")
        tier = threshold.get("tier")
        if not isinstance(tier, str) or not tier:
            raise InvalidTrustPolicyError(f"policy.content.level_thresholds.{index}.tier is required")
        max_score = _as_number(
            threshold.get("max_score"),
            f"policy.content.level_thresholds.{index}.max_score",
        )
        parsed_thresholds.append({"tier": tier, "max_score": max_score})

    parsed_thresholds.sort(key=lambda threshold: float(threshold["max_score"]))

    return {
        "score_floor": floor,
        "score_ceiling": ceiling,
        "default_score": default,
        "signal_weights": signal_weights,
        "decay_rules": decay_rules,
        "level_thresholds": parsed_thresholds,
    }


def _tier_for_score(score: int, thresholds: Sequence[Mapping[str, Any]]) -> str:
    for threshold in thresholds:
        if score <= float(threshold["max_score"]):
            return str(threshold["tier"])
    raise InvalidTrustPolicyError("policy.content.level_thresholds does not cover score")


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _canonical_signal_rows(active_signals: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        active_signals,
        key=lambda row: (
            row["observed_at"],
            row["created_at"],
            str(row["id"]),
        ),
    )


def _dedupe_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["member_id"]),
        row["signal_type"],
        row["scope_kind"],
        row["scope_id"],
        row["observed_at"].isoformat(),
        row["source_actor_kind"],
        row["source_actor_id"],
        _canonical_json(_as_mapping(row["value"], "trust_signal.value")),
    )


def _signal_magnitude(row: Mapping[str, Any]) -> float:
    value = _as_mapping(row["value"], "trust_signal.value")
    magnitude = value.get("magnitude", 1)
    if isinstance(magnitude, bool) or not isinstance(magnitude, (int, float)):
        raise InvalidTrustPolicyError("trust_signal.value.magnitude must be numeric")
    return float(magnitude)


def compute_score(
    active_signals: Sequence[Mapping[str, Any]],
    policy_content: Mapping[str, Any],
) -> tuple[int, str, dict[str, Any]]:
    config = _policy_config(policy_content)
    score = float(config["default_score"])
    included: list[Mapping[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    deduplicated_count = 0

    for row in _canonical_signal_rows(active_signals):
        key = _dedupe_key(row)
        if key in seen:
            deduplicated_count += 1
            continue
        seen.add(key)
        included.append(row)
        weight = _as_number(
            config["signal_weights"].get(row["signal_type"], 0),
            f"policy.content.signal_weights.{row['signal_type']}",
        )
        score += weight * _signal_magnitude(row)

    bounded = int(round(max(config["score_floor"], min(config["score_ceiling"], score))))
    tier = _tier_for_score(bounded, config["level_thresholds"])
    summary = {
        "signal_ids": [str(row["id"]) for row in included],
        "count": len(included),
        "included_signal_types": sorted({str(row["signal_type"]) for row in included}),
        "deduplicated_count": deduplicated_count,
    }
    return bounded, tier, summary


def evaluate_trust(
    signals: TrustSignalsInput,
    policy_content: Mapping[str, Any],
) -> tuple[int, str]:
    config = _policy_config(policy_content)
    weights = config["signal_weights"]
    score = float(config["default_score"])
    score += signals.discord_account_age_days * _as_number(
        weights.get("discord_account_age_days", 0),
        "policy.content.signal_weights.discord_account_age_days",
    )
    if signals.has_avatar:
        score += _as_number(weights.get("has_avatar", 0), "policy.content.signal_weights.has_avatar")
    if signals.has_verified_badge:
        score += _as_number(
            weights.get("has_verified_badge", 0),
            "policy.content.signal_weights.has_verified_badge",
        )
    for flag in signals.account_flags:
        score += _as_number(
            weights.get(f"flag:{flag}", 0),
            f"policy.content.signal_weights.flag:{flag}",
        )

    bounded = int(round(max(config["score_floor"], min(config["score_ceiling"], score))))
    return bounded, _tier_for_score(bounded, config["level_thresholds"])


def validate_trust_signal_scope(request: TrustSignalCreate) -> None:
    if request.scope.scope_kind == "global" and request.scope.scope_id is not None:
        raise InvalidTrustSignalScopeError("global scope must not include scope_id")
    if request.scope.scope_kind in {"chapter", "member"} and not request.scope.scope_id:
        raise InvalidTrustSignalScopeError("chapter/member scope requires scope_id")


class TrustService:
    def __init__(
        self,
        trust_repo: TrustRepository,
        members_repo: MembersRepository,
        policies_repo: PoliciesRepository,
        mutations_callable,
    ) -> None:
        self._trust_repo = trust_repo
        self._members_repo = members_repo
        self._policies_repo = policies_repo
        self._mutations_callable = mutations_callable

    def _call_mutation(self, **kwargs: Any) -> MutationResult:
        result = self._mutations_callable(**kwargs)
        if callable(result):
            result = result(**kwargs)
        return result

    def create_trust_signal(
        self,
        request: TrustSignalCreate,
        actor: ActorIdentity,
    ) -> tuple[TrustSignalRead, MutationResult]:
        if actor.actor_kind == "system":
            raise InvalidTrustSignalActorError()
        validate_trust_signal_scope(request)

        signal_id = uuid4()
        persisted_scope = request.scope.to_persisted_json()
        action_payload = request.model_dump(mode="json")
        change_payload = {
            "id": str(signal_id),
            "member_id": str(request.member_id),
            "signal_type": request.signal_type,
            "scope": action_payload["scope"],
            "value": action_payload["value"],
            "source_actor_kind": actor.actor_kind,
            "source_actor_id": actor.actor_id,
            "observed_at": action_payload["observed_at"],
            "expires_at": action_payload["expires_at"],
        }

        with self._trust_repo.db.connection() as connection:
            member = self._members_repo._fetch_member_by_id_on(
                connection,
                request.member_id,
            )
            if member is None:
                raise MemberNotFoundError(member_id=request.member_id)
            if is_synthetic_member(member):
                _raise_synthetic_trust_subject()

        created_row: dict[str, Any] | None = None

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            nonlocal created_row
            row = self._trust_repo._insert_trust_signal_on(
                connection,
                row={
                    "id": signal_id,
                    "member_id": request.member_id,
                    "signal_type": request.signal_type,
                    "scope_kind": request.scope.scope_kind,
                    "scope_id": request.scope.scope_id,
                    "scope": persisted_scope,
                    "value": request.value,
                    "source_actor_kind": actor.actor_kind,
                    "source_actor_id": actor.actor_id,
                    "observed_at": request.observed_at,
                    "expires_at": request.expires_at,
                },
            )
            created_row = row
            return StateChangeDraft(
                change_type=TRUST_SIGNAL_CREATE_CHANGE,
                payload_json=change_payload,
                diff_json={
                    "signal_type": request.signal_type,
                    "scope": action_payload["scope"],
                    "value": action_payload["value"],
                    "observed_at": action_payload["observed_at"],
                    "expires_at": action_payload["expires_at"],
                },
            )

        result = self._call_mutation(
            aggregate_type=TRUST_SIGNAL_AGGREGATE_TYPE,
            aggregate_id=str(signal_id),
            request=_make_request(
                expected_version=0,
                actor=actor,
                request_surface="api:/api/v1/trust/signals",
            ),
            action_type=TRUST_SIGNAL_CREATE_ACTION,
            action_payload=action_payload,
            payload_allowlist={
                "member_id",
                "signal_type",
                "scope",
                "value",
                "expires_at",
                "observed_at",
                "observation_timestamp",
            },
            mutate_projection=mutate_projection,
            scope_kind=request.scope.scope_kind,
            scope_id=request.scope.scope_id,
        )
        if created_row is None:
            raise RuntimeError("failed to insert trust signal")
        return _signal_from_row(created_row), result

    def compute_trust(
        self,
        member_id: UUID,
        signals: TrustSignalsInput,
        actor: ActorIdentity,
    ) -> tuple[TrustProfileRead, MutationResult | None, bool]:
        computed_at = datetime.now(UTC)
        with self._trust_repo.db.connection() as connection:
            member = self._members_repo._fetch_member_by_id_on(connection, member_id)
            if member is None:
                raise MemberNotFoundError(member_id=member_id)
            if is_synthetic_member(member):
                _raise_synthetic_trust_subject()
            existing = self._trust_repo._fetch_trust_profile_by_member_id_on(
                connection,
                member_id,
            )
            if existing is not None:
                return _profile_from_row(existing), None, False
            policy = self._policies_repo._fetch_latest_version_on(
                connection,
                TRUST_POLICY_TYPE,
                "global",
                None,
            )

        if policy is None:
            raise NoTrustPolicyConfiguredError()

        content = _as_mapping(policy["content"], "policy.content")
        score, tier = evaluate_trust(signals, content)
        signal_payload = signals.model_dump(
            mode="json",
            exclude={"originating_actor_kind", "originating_actor_id"},
        )

        def reread_existing() -> tuple[TrustProfileRead, None, bool]:
            with self._trust_repo.db.connection() as connection:
                row = self._trust_repo._fetch_trust_profile_by_member_id_on(
                    connection,
                    member_id,
                )
            if row is None:
                raise TrustProfileNotFoundError(member_id)
            return _profile_from_row(row), None, False

        def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
            self._trust_repo._upsert_trust_profile_for_recompute_on(
                connection,
                row={
                    "member_id": member_id,
                    "score": score,
                    "tier": tier,
                    "signals": signal_payload,
                    "policy_version_id": policy["id"],
                    "config_version": policy["version_number"],
                    "computed_at": computed_at,
                },
            )
            return StateChangeDraft(
                change_type="trust_profile.computed",
                payload_json={
                    "member_id": str(member_id),
                    "score": score,
                    "tier": tier,
                    "signals": signal_payload,
                    "policy_version_id": str(policy["id"]),
                    "config_version": policy["version_number"],
                    "originating_actor_kind": signals.originating_actor_kind,
                    "originating_actor_id": signals.originating_actor_id,
                },
            )

        try:
            result = self._call_mutation(
                aggregate_type=TRUST_PROFILE_AGGREGATE_TYPE,
                aggregate_id=str(member_id),
                request=_make_request(
                    expected_version=0,
                    actor=actor,
                    request_surface=f"api:/api/v1/trust/compute/{member_id}",
                ),
                action_type="trust_profile.compute",
                action_payload=signals.model_dump(mode="json"),
                payload_allowlist=set(signals.model_dump(mode="json").keys()),
                mutate_projection=mutate_projection,
                scope_kind="global",
                scope_id=None,
            )
        except (StaleMutationError, errors.UniqueViolation) as error:
            try:
                return reread_existing()
            except TrustProfileNotFoundError:
                raise error from None

        with self._trust_repo.db.connection() as connection:
            row = _fetch_profile_row(self._trust_repo, connection, member_id)
        return _profile_from_row(row), result, True

    def _recompute_once_on(
        self,
        connection: Connection[Any],
        member_id: UUID,
        actor: ActorIdentity,
        *,
        as_of: datetime,
    ) -> tuple[TrustProfileRead, MutationResult]:
        member = self._members_repo._fetch_member_by_id_on(connection, member_id)
        if member is None:
            raise MemberNotFoundError(member_id=member_id)
        if is_synthetic_member(member):
            _raise_synthetic_trust_subject()

        existing = self._trust_repo._get_trust_profile_for_update_on(
            connection,
            member_id,
        )
        expected_version = 0 if existing is None else int(existing["version"])
        policy = self._policies_repo._fetch_latest_version_on(
            connection,
            TRUST_POLICY_TYPE,
            "global",
            None,
        )
        if policy is None:
            raise NoTrustPolicyConfiguredError()

        signals = self._trust_repo._list_active_signals_for_member_on(
            connection,
            member_id=member_id,
            as_of=as_of,
        )
        score, tier, signal_summary = compute_score(
            signals,
            _as_mapping(policy["content"], "policy.content"),
        )
        old_values = {
            "score": None if existing is None else int(existing["score"]),
            "tier": None if existing is None else existing["tier"],
            "policy_version_id": (
                None if existing is None else str(existing["policy_version_id"])
            ),
            "config_version": (
                None if existing is None else int(existing["config_version"])
            ),
            "signal_ids": (
                [] if existing is None else list(existing["signals"].get("signal_ids", []))
            ),
        }
        new_values = {
            "score": score,
            "tier": tier,
            "policy_version_id": str(policy["id"]),
            "config_version": int(policy["version_number"]),
            "signal_ids": signal_summary["signal_ids"],
        }

        def mutate_projection(active_connection: Connection[Any]) -> StateChangeDraft:
            self._trust_repo._upsert_trust_profile_for_recompute_on(
                active_connection,
                row={
                    "member_id": member_id,
                    "score": score,
                    "tier": tier,
                    "signals": signal_summary,
                    "policy_version_id": policy["id"],
                    "config_version": policy["version_number"],
                    "computed_at": as_of,
                },
            )
            return StateChangeDraft(
                change_type=TRUST_RECOMPUTE_CHANGE,
                payload_json={
                    "member_id": str(member_id),
                    "score": score,
                    "tier": tier,
                    "policy_version_id": str(policy["id"]),
                    "config_version": int(policy["version_number"]),
                    "signal_count": signal_summary["count"],
                },
                diff_json={
                    key: {"old": old_values[key], "new": new_values[key]}
                    for key in old_values
                },
            )

        result = self._call_mutation(
            connection=connection,
            aggregate_type=TRUST_PROFILE_AGGREGATE_TYPE,
            aggregate_id=str(member_id),
            request=_make_request(
                expected_version=expected_version,
                actor=actor,
                request_surface=f"api:/api/v1/trust/recompute/{member_id}",
            ),
            action_type=TRUST_RECOMPUTE_ACTION,
            action_payload={"member_id": str(member_id)},
            payload_allowlist={"member_id"},
            mutate_projection=mutate_projection,
            scope_kind="member",
            scope_id=str(member_id),
        )
        row = _fetch_profile_row(self._trust_repo, connection, member_id)
        return _profile_from_row(row), result

    def recompute_trust_profile(
        self,
        member_id: UUID,
        actor: ActorIdentity,
    ) -> tuple[TrustProfileRead, MutationResult]:
        as_of = datetime.now(UTC)
        for attempt in range(2):
            try:
                with self._trust_repo.db.transaction() as connection:
                    return self._recompute_once_on(
                        connection,
                        member_id,
                        actor,
                        as_of=as_of,
                    )
            except StaleMutationError:
                if attempt == 1:
                    raise TrustRecomputeConflictError() from None
        raise TrustRecomputeConflictError()

    def get_trust_profile(
        self,
        member_id: UUID,
    ) -> tuple[TrustProfileRead, str]:
        with self._trust_repo.db.connection() as connection:
            read = _profile_from_row(
                _fetch_profile_row(self._trust_repo, connection, member_id)
            )
        return read, f'"{read.version}"'


__all__ = [
    "TRUST_POLICY_TYPE",
    "TRUST_RECOMPUTE_ACTION",
    "TRUST_RECOMPUTE_CHANGE",
    "TRUST_SIGNAL_CREATE_ACTION",
    "TRUST_SIGNAL_CREATE_CHANGE",
    "TrustService",
    "compute_score",
    "evaluate_trust",
    "validate_trust_signal_scope",
]
