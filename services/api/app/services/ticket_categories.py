from __future__ import annotations

import re
from collections import deque
from typing import Any

from app.contracts.ticket_categories import (
    InvalidTicketSlaRulesError,
    InvalidTicketStateMachineError,
)

STATE_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
CATEGORY_PAYLOAD_ALLOWLIST = {
    "name",
    "routing_scope",
    "privacy_level",
    "state_machine",
    "sla_rules",
}


def _build_changed_fields(current: dict[str, Any], updated: dict[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key in CATEGORY_PAYLOAD_ALLOWLIST:
        if current[key] != updated[key]:
            diff[key] = {"old": current[key], "new": updated[key]}
    return diff


def validate_state_machine(state_machine: dict[str, Any]) -> dict[str, Any]:
    if state_machine.get("schema_version") != 1:
        raise InvalidTicketStateMachineError("state_machine.schema_version must equal 1")

    states = state_machine.get("states")
    if not isinstance(states, list) or not states:
        raise InvalidTicketStateMachineError("state_machine.states must be a non-empty list")

    edges = state_machine.get("edges")
    if not isinstance(edges, list):
        raise InvalidTicketStateMachineError("state_machine.edges must be a list")

    state_map: dict[str, dict[str, Any]] = {}
    adjacency: dict[str, list[dict[str, Any]]] = {}
    reverse_adjacency: dict[str, set[str]] = {}
    terminal_states: set[str] = set()

    for raw_state in states:
        key = raw_state.get("key")
        label = raw_state.get("label")
        terminal = bool(raw_state.get("terminal"))
        if not isinstance(key, str) or not STATE_KEY_PATTERN.fullmatch(key):
            raise InvalidTicketStateMachineError(
                "state keys must match ^[a-z0-9_]+$"
            )
        if key in state_map:
            raise InvalidTicketStateMachineError(f"duplicate state key: {key}")
        if not isinstance(label, str) or not label.strip():
            raise InvalidTicketStateMachineError(f"state {key} requires a non-empty label")
        if len(label) > 80:
            raise InvalidTicketStateMachineError(f"state {key} label exceeds 80 characters")
        state_map[key] = raw_state
        adjacency[key] = []
        reverse_adjacency[key] = set()
        if terminal:
            terminal_states.add(key)

    if not terminal_states:
        raise InvalidTicketStateMachineError("state_machine must contain at least one terminal state")

    initial_state = state_machine.get("initial_state")
    if initial_state not in state_map:
        raise InvalidTicketStateMachineError("initial_state must reference a known state")
    if bool(state_map[initial_state].get("terminal")):
        raise InvalidTicketStateMachineError("initial_state must not be terminal")

    seen_edges: set[tuple[str, str, str]] = set()
    for raw_edge in edges:
        from_state = raw_edge.get("from")
        to_state = raw_edge.get("to")
        action = raw_edge.get("action")
        if from_state not in state_map or to_state not in state_map:
            raise InvalidTicketStateMachineError("edge references an unknown state")
        if not isinstance(action, str) or not action.strip():
            raise InvalidTicketStateMachineError("edge action must be non-empty")
        if bool(state_map[from_state].get("terminal")):
            raise InvalidTicketStateMachineError(
                f"terminal state {from_state} may not have outgoing edges"
            )
        edge_key = (str(from_state), str(action), str(to_state))
        if edge_key in seen_edges:
            raise InvalidTicketStateMachineError(
                f"duplicate edge: {from_state} --{action}--> {to_state}"
            )
        seen_edges.add(edge_key)
        adjacency[from_state].append(raw_edge)
        reverse_adjacency[to_state].add(from_state)

    visited: set[str] = set()
    queue = deque([str(initial_state)])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for edge in adjacency[current]:
            queue.append(str(edge["to"]))

    disconnected = sorted(set(state_map) - visited)
    if disconnected:
        raise InvalidTicketStateMachineError(
            f"states are not reachable from initial_state: {', '.join(disconnected)}"
        )

    reverse_visited: set[str] = set()
    reverse_queue = deque(terminal_states)
    while reverse_queue:
        current = reverse_queue.popleft()
        if current in reverse_visited:
            continue
        reverse_visited.add(current)
        for predecessor in reverse_adjacency[current]:
            reverse_queue.append(predecessor)

    missing_terminal_path = sorted(
        state_key
        for state_key, state in state_map.items()
        if not bool(state.get("terminal")) and state_key not in reverse_visited
    )
    if missing_terminal_path:
        raise InvalidTicketStateMachineError(
            "non-terminal states must have a path to a terminal state: "
            + ", ".join(missing_terminal_path)
        )

    return state_machine


def find_state_path(
    state_machine: dict[str, Any],
    start_state: str,
    target_state: str,
) -> list[dict[str, Any]] | None:
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for edge in state_machine.get("edges", []):
        adjacency.setdefault(str(edge["from"]), []).append(edge)

    queue: deque[tuple[str, list[dict[str, Any]]]] = deque([(start_state, [])])
    seen: set[str] = set()
    while queue:
        current, path = queue.popleft()
        if current == target_state:
            return path
        if current in seen:
            continue
        seen.add(current)
        for edge in adjacency.get(current, []):
            queue.append((str(edge["to"]), [*path, edge]))
    return None


def validate_sla_rules(
    sla_rules: dict[str, Any],
    state_machine: dict[str, Any],
) -> dict[str, Any]:
    if sla_rules.get("schema_version") != 1:
        raise InvalidTicketSlaRulesError("sla_rules.schema_version must equal 1")

    rules = sla_rules.get("rules")
    if not isinstance(rules, list):
        raise InvalidTicketSlaRulesError("sla_rules.rules must be a list")

    state_keys = {state["key"] for state in state_machine["states"]}
    seen_rule_keys: set[str] = set()
    valid_consequences = {
        "notify_owner",
        "notify_scope",
        "flag_for_review",
        "auto_escalate",
    }

    for rule in rules:
        key = rule.get("key")
        if not isinstance(key, str) or not key or len(key) > 64:
            raise InvalidTicketSlaRulesError("sla_rules keys must be 1-64 characters")
        if key in seen_rule_keys:
            raise InvalidTicketSlaRulesError(f"duplicate sla_rules key: {key}")
        seen_rule_keys.add(key)

        trigger_states = rule.get("states")
        if not isinstance(trigger_states, list) or not trigger_states:
            raise InvalidTicketSlaRulesError(f"sla rule {key} requires at least one state")
        for state in trigger_states:
            if state not in state_keys:
                raise InvalidTicketSlaRulesError(f"sla rule {key} references unknown state {state}")

        thresholds = rule.get("thresholds")
        if not isinstance(thresholds, list) or not thresholds:
            raise InvalidTicketSlaRulesError(
                f"sla rule {key} requires at least one threshold"
            )

        last_elapsed = 0
        for threshold in thresholds:
            elapsed_seconds = threshold.get("elapsed_seconds")
            consequence = threshold.get("consequence")
            target_state = threshold.get("target_state")
            if not isinstance(elapsed_seconds, int) or elapsed_seconds <= 0:
                raise InvalidTicketSlaRulesError(
                    f"sla rule {key} thresholds must use positive elapsed_seconds"
                )
            if elapsed_seconds <= last_elapsed:
                raise InvalidTicketSlaRulesError(
                    f"sla rule {key} thresholds must increase strictly"
                )
            last_elapsed = elapsed_seconds
            if consequence not in valid_consequences:
                raise InvalidTicketSlaRulesError(
                    f"sla rule {key} has invalid consequence {consequence}"
                )
            if consequence == "auto_escalate":
                if target_state not in state_keys:
                    raise InvalidTicketSlaRulesError(
                        f"sla rule {key} auto_escalate requires a known target_state"
                    )
                for state in trigger_states:
                    if find_state_path(state_machine, str(state), str(target_state)) is None:
                        raise InvalidTicketSlaRulesError(
                            f"sla rule {key} target_state {target_state} is unreachable from {state}"
                        )
            elif target_state is not None:
                raise InvalidTicketSlaRulesError(
                    f"sla rule {key} target_state is only allowed for auto_escalate"
                )

    return sla_rules
