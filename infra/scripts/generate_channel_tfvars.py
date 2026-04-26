#!/usr/bin/env python3
"""Generate channel.auto.tfvars.json from resolved platform channel JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resolve_platform_channel import ChannelError, write_error


DEFAULT_VULTR_AGENT_PLAN = "vc2-2c-4gb"
DEFAULT_REMOTE_KUBECONFIG_PATH = "/root/humility-k3s.yaml"


def _load_resolved(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ChannelError("file_not_found", "resolved", f"resolved channel file not found: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("resolved channel JSON must contain an object")
    return data


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _cluster_name(channel_id: str) -> str:
    return f"humility-{channel_id}"


def _kubeconfig_path(channel_id: str, k3d: dict[str, Any]) -> str:
    value = k3d.get("kubeconfig_path")
    if value is None:
        return f"~/.kube/{_cluster_name(channel_id)}.yaml"
    return _required_string(value, "cluster.k3d.kubeconfig_path")


def _ssh_key_ids(vultr_vms: dict[str, Any]) -> list[str]:
    raw = vultr_vms.get("ssh_key_ids", [])
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("cluster.vultr_vms.ssh_key_ids must be a list of strings")
    return raw


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, name)


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a list of strings")
    return value


def tfvars_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    cluster = _required_mapping(resolved.get("cluster"), "cluster")
    channel_id = _required_string(resolved.get("id"), "id")
    target = _required_string(cluster.get("target"), "cluster.target")

    payload: dict[str, Any] = {
        "channel_id": channel_id,
        "cluster_distribution": _required_string(cluster.get("distribution"), "cluster.distribution"),
        "cluster_k3s_version": _required_string(cluster.get("k3s_version"), "cluster.k3s_version"),
        "cluster_target": target,
    }

    if target == "k3d-local":
        k3d = _required_mapping(cluster.get("k3d"), "cluster.k3d")
        payload.update(
            {
                "k3d_agents": _required_int(k3d.get("agents"), "cluster.k3d.agents"),
                "k3d_kubeconfig_path": _kubeconfig_path(channel_id, k3d),
                "k3d_registry_name": _required_string(
                    k3d.get("registry_name"),
                    "cluster.k3d.registry_name",
                ),
                "k3d_servers": _required_int(k3d.get("servers"), "cluster.k3d.servers"),
            }
        )
        return payload

    if target == "vultr-vms":
        vultr_vms = _required_mapping(cluster.get("vultr_vms"), "cluster.vultr_vms")
        servers = _required_mapping(vultr_vms.get("servers"), "cluster.vultr_vms.servers")
        agents = _required_mapping(vultr_vms.get("agents"), "cluster.vultr_vms.agents")
        payload.update(
            {
                "vultr_allowed_ssh_cidrs": _string_list(
                    vultr_vms.get("allowed_ssh_cidrs", []),
                    "cluster.vultr_vms.allowed_ssh_cidrs",
                ),
                "vultr_agent_count": _required_int(agents.get("count"), "cluster.vultr_vms.agents.count"),
                "vultr_agent_plan": _required_string(
                    agents.get("plan", DEFAULT_VULTR_AGENT_PLAN),
                    "cluster.vultr_vms.agents.plan",
                ),
                "vultr_firewall_name": _optional_string(
                    vultr_vms.get("firewall_name"),
                    "cluster.vultr_vms.firewall_name",
                ),
                "vultr_region": _required_string(vultr_vms.get("region"), "cluster.vultr_vms.region"),
                "vultr_remote_kubeconfig_path": _required_string(
                    vultr_vms.get("remote_kubeconfig_path", DEFAULT_REMOTE_KUBECONFIG_PATH),
                    "cluster.vultr_vms.remote_kubeconfig_path",
                ),
                "vultr_server_count": _required_int(servers.get("count"), "cluster.vultr_vms.servers.count"),
                "vultr_server_plan": _required_string(servers.get("plan"), "cluster.vultr_vms.servers.plan"),
                "vultr_ssh_key_ids": _ssh_key_ids(vultr_vms),
            }
        )
        return payload

    raise ValueError("cluster.target must be k3d-local or vultr-vms")


def render_tfvars(resolved: dict[str, Any]) -> str:
    return json.dumps(tfvars_payload(resolved), indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved", required=True, help="path to resolved channel JSON")
    parser.add_argument("--out", required=True, help="output tfvars JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        resolved = _load_resolved(Path(args.resolved))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_tfvars(resolved), encoding="utf-8")
        return 0
    except ChannelError as exc:
        write_error(exc)
        return 1
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        write_error(ChannelError("schema_invalid", "resolved", str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
