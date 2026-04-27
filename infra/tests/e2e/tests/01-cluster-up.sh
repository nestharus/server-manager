#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "01-cluster-up" "local k3d cluster and CoreDNS"

require_cluster
expected_nodes="$(python3 "${REPO_ROOT}/infra/scripts/resolve_platform_channel.py" --channel local | jq -r '.cluster.k3d.servers + .cluster.k3d.agents')"
actual_nodes="$(kubectl_cmd get nodes --no-headers | awk 'NF { count += 1 } END { print count + 0 }')"
[[ "$actual_nodes" == "$expected_nodes" ]] || e2e_fail "node count ${actual_nodes}, expected ${expected_nodes}"
e2e_pass "node count matches channel contract (${actual_nodes})"

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
