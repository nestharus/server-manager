#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "01-cluster-up" "local k3d cluster and CoreDNS"

require_cluster
nodes_json="$(kubectl_cmd get nodes -o json)"
CLUSTER_FIXTURE="${REPO_ROOT}/infra/tests/fixtures/channels/local_platform_bootstrap.yml" \
NODES_JSON="$nodes_json" \
python3 <<'PY' || e2e_fail "live node topology does not match bootstrap fixture"
import json
import os
from pathlib import Path

import yaml

fixture = yaml.safe_load(Path(os.environ["CLUSTER_FIXTURE"]).read_text(encoding="utf-8"))
cluster = fixture["k3d_cluster"]["name"]
required_roles = fixture["k3d_cluster"]["required_node_roles"]
node_names = [item["metadata"]["name"] for item in json.loads(os.environ["NODES_JSON"])["items"]]

missing = [
    role
    for role in required_roles
    if not any(f"{cluster}-{role}" in node_name for node_name in node_names)
]
if missing:
    raise SystemExit(f"missing k3d node roles: {', '.join(missing)}; nodes={node_names}")
PY
actual_nodes="$(printf '%s' "$nodes_json" | jq '.items | length')"
e2e_pass "live nodes include bootstrap fixture roles (${actual_nodes} nodes)"

kubectl_cmd wait nodes --all --for=condition=Ready --timeout=180s >/dev/null
e2e_pass "all nodes Ready"

kubectl_cmd -n kube-system rollout status deployment/coredns --timeout=180s >/dev/null
e2e_pass "CoreDNS Deployment Available"

kubectl_cmd -n kube-system delete pod e2e-cluster-dns --ignore-not-found >/dev/null
kubectl_cmd -n kube-system run e2e-cluster-dns --restart=Never --image=busybox:1.37.0 \
  --command -- nslookup kubernetes.default.svc.cluster.local >/dev/null
kubectl_cmd -n kube-system wait pod/e2e-cluster-dns --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null
kubectl_cmd -n kube-system logs e2e-cluster-dns | tee "$(e2e_log_path cluster-dns)" >/dev/null
kubectl_cmd -n kube-system delete pod e2e-cluster-dns --ignore-not-found >/dev/null
e2e_pass "cluster.local DNS resolves from inside cluster"
e2e_finish
