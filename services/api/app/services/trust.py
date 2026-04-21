from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from psycopg import Connection, errors

from app.contracts.actor import ActorIdentity
from app.contracts.members import MemberNotFoundError
from app.contracts.mutations import MutationRequest, MutationResult, StaleMutationError, StateChangeDraft
from app.contracts.trust import (
    InvalidTrustPolicyError,
    NoTrustPolicyConfiguredError,
    TrustProfileNotFoundError,
    TrustProfileRead,
    TrustSignalsInput,
)
from app.repositories.db import PostgresDatabase
from app.repositories.members import fetch_member_by_id
from app.repositories.policies import fetch_latest_version
from app.repositories.trust import (
    _insert_trust_profile,
    fetch_trust_profile_by_member_id,
)
from app.services.mutations import mutate_entity


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
        version=int(row["version"]),
    )


def _fetch_profile_row(
    connection: Connection[Any],
    member_id: UUID,
) -> dict[str, Any]:
    row = fetch_trust_profile_by_member_id(connection, member_id)
    if row is None:
        raise TrustProfileNotFoundError(member_id)
    return row


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidTrustPolicyError(f"{path} must be an object")
    return value


def _as_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTrustPolicyError(f"{path} must be numeric")
    return float(value)


def _required_number(rules: Mapping[str, Any], key: str) -> float:
    if key not in rules:
        raise InvalidTrustPolicyError(f"rules.{key} is required")
    return _as_number(rules[key], f"rules.{key}")


def _age_weight(value: Any) -> tuple[float, float | None]:
    return _as_number(value, "rules.weights.discord_account_age_days"), None


def _tier_for_score(score: int, tiers_value: Any) -> str:
    if not isinstance(tiers_value, Sequence) or isinstance(tiers_value, (str, bytes)):
        raise InvalidTrustPolicyError("rules.tiers must be an array")
    if not tiers_value:
        raise InvalidTrustPolicyError("rules.tiers must not be empty")
    for index, tier_value in enumerate(tiers_value):
        tier = _as_mapping(tier_value, f"rules.tiers.{index}")
        name = tier.get("name")
        if not isinstance(name, str) or not name:
            raise InvalidTrustPolicyError(f"rules.tiers.{index}.name is required")
        max_score = _as_number(
            tier.get("max_score"),
            f"rules.tiers.{index}.max_score",
        )
        if score <= max_score:
            return name
    raise InvalidTrustPolicyError("rules.tiers does not cover score")


def evaluate_trust(
    signals: TrustSignalsInput,
    policy_rules: Mapping[str, Any],
) -> tuple[int, str]:
    rules = _as_mapping(policy_rules, "rules")
    floor = _required_number(rules, "score_floor")
    ceiling = _required_number(rules, "score_ceiling")
    score = _required_number(rules, "default_score")
    if floor > ceiling:
        raise InvalidTrustPolicyError("rules.score_floor must be <= rules.score_ceiling")

    weights_raw = rules.get("weights")
    if weights_raw is None:
        raise InvalidTrustPolicyError("weights missing")
    weights = _as_mapping(weights_raw, "rules.weights")
    age_per_day, age_max = _age_weight(weights.get("discord_account_age_days"))
    age_score = signals.discord_account_age_days * age_per_day
    if age_max is not None:
        age_score = min(age_score, age_max)
    score += age_score

    avatar_weight = _as_number(weights.get("has_avatar"), "rules.weights.has_avatar")
    verified_weight = _as_number(
        weights.get("has_verified_badge"),
        "rules.weights.has_verified_badge",
    )
    if signals.has_avatar:
        score += avatar_weight
    if signals.has_verified_badge:
        score += verified_weight

    flag_rules = _as_mapping(rules.get("flags"), "rules.flags")
    for flag in signals.account_flags:
        if flag in flag_rules:
            score += _as_number(flag_rules[flag], f"rules.flags.{flag}")

    bounded = int(round(max(floor, min(ceiling, score))))
    return bounded, _tier_for_score(bounded, rules.get("tiers"))


def compute_trust(
    db: PostgresDatabase,
    member_id: UUID,
    signals: TrustSignalsInput,
    actor: ActorIdentity,
) -> tuple[TrustProfileRead, MutationResult | None, bool]:
    with db.connection() as connection:
        if fetch_member_by_id(connection, member_id) is None:
            raise MemberNotFoundError(member_id=member_id)
        existing = fetch_trust_profile_by_member_id(connection, member_id)
        if existing is not None:
            return _profile_from_row(existing), None, False
        policy = fetch_latest_version(connection, "trust", "global", None)

    if policy is None:
        raise NoTrustPolicyConfiguredError()

    content = _as_mapping(policy["content"], "policy.content")
    if "rules" not in content:
        raise InvalidTrustPolicyError("policy.content.rules is required")
    score, tier = evaluate_trust(signals, _as_mapping(content["rules"], "rules"))
    signal_payload = signals.model_dump(
        mode="json",
        exclude={"originating_actor_kind", "originating_actor_id"},
    )

    def reread_existing() -> tuple[TrustProfileRead, None, bool]:
        with db.connection() as connection:
            row = fetch_trust_profile_by_member_id(connection, member_id)
        if row is None:
            raise TrustProfileNotFoundError(member_id)
        return _profile_from_row(row), None, False

    def mutate_projection(connection: Connection[Any]) -> StateChangeDraft:
        _insert_trust_profile(
            connection,
            row={
                "member_id": member_id,
                "score": score,
                "tier": tier,
                "signals": signal_payload,
                "policy_version_id": policy["id"],
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
                "originating_actor_kind": signals.originating_actor_kind,
                "originating_actor_id": signals.originating_actor_id,
            },
        )

    try:
        result = mutate_entity(
            db=db,
            aggregate_type="trust_profile",
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

    with db.connection() as connection:
        row = _fetch_profile_row(connection, member_id)
    return _profile_from_row(row), result, True


def get_trust_profile(
    db: PostgresDatabase,
    member_id: UUID,
) -> tuple[TrustProfileRead, str]:
    with db.connection() as connection:
        read = _profile_from_row(_fetch_profile_row(connection, member_id))
    return read, f'"{read.version}"'


__all__ = [
    "compute_trust",
    "evaluate_trust",
    "get_trust_profile",
]
