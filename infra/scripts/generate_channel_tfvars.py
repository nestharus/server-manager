#!/usr/bin/env python3
"""Generate channel.auto.tfvars.json from resolved channel JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TFVAR_KEYS = (
    "channel_id",
    "region",
    "vpc_v4_subnet",
    "vpc_v4_subnet_mask",
    "cluster_label",
    "cluster_kubernetes_version",
    "node_plan",
    "node_quantity",
    "ha_controlplanes",
    "enable_firewall",
)


def _load_resolved(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("resolved channel JSON must contain an object")
    return data


def _required_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _single_node_pool(cluster: dict[str, Any]) -> dict[str, Any]:
    node_pools = cluster.get("node_pools")
    if not isinstance(node_pools, list) or not node_pools:
        raise ValueError("cluster.node_pools must contain exactly one pool")
    if len(node_pools) != 1:
        raise ValueError("cluster.node_pools must contain exactly one pool")

    first = node_pools[0]
    if not isinstance(first, dict):
        raise ValueError("cluster.node_pools[0] must be an object")
    return first


def tfvars_payload(resolved: dict[str, Any]) -> dict[str, Any]:
    platform = _required_mapping(resolved.get("platform"), "platform")
    network = _required_mapping(platform.get("network"), "platform.network")
    cluster = _required_mapping(resolved.get("cluster"), "cluster")
    node_pool = _single_node_pool(cluster)

    return {
        "channel_id": resolved["id"],
        "region": platform["region"],
        "vpc_v4_subnet": network["v4_subnet"],
        "vpc_v4_subnet_mask": network["v4_subnet_mask"],
        "cluster_label": cluster["label"],
        "cluster_kubernetes_version": cluster["kubernetes_version"],
        "node_plan": node_pool["plan"],
        "node_quantity": node_pool["count"],
        "ha_controlplanes": cluster["ha_controlplanes"],
        "enable_firewall": cluster["enable_firewall"],
    }


def render_tfvars(resolved: dict[str, Any]) -> str:
    payload = tfvars_payload(resolved)
    ordered_payload = {key: payload[key] for key in TFVAR_KEYS}
    return json.dumps(ordered_payload, indent=2) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved", required=True, help="path to resolved channel JSON")
    parser.add_argument("--out", required=True, help="output tfvars JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved = _load_resolved(Path(args.resolved))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_tfvars(resolved), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
