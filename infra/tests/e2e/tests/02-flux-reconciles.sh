#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "02-flux-reconciles" "Flux source and Kustomization"

require_cluster
kubectl_cmd -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=300s >/dev/null
e2e_pass "GitRepository/humility-local Ready=True"
kubectl_cmd -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=900s >/dev/null
e2e_pass "Kustomization/humility-local Ready=True"

marker_sha="$(kubectl_cmd -n humility-gitops-sentinel get configmap gitops-snapshot-marker -o jsonpath='{.data.source_sha}' 2>/dev/null || true)"
[[ -n "$marker_sha" ]] || e2e_fail "gitops snapshot marker missing source_sha"
e2e_pass "seeded snapshot marker exists (${marker_sha})"
e2e_finish
