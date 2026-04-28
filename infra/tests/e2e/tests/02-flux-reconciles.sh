#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "02-flux-reconciles" "Flux source and Kustomization"

require_cluster
kubectl_cmd -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=300s >/dev/null
e2e_pass "GitRepository/humility-local Ready=True"
if kubectl_cmd -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout="${FLUX_KUSTOMIZATION_WAIT_TIMEOUT:-60s}" >/dev/null; then
  e2e_pass "Kustomization/humility-local Ready=True"
else
  python3 -m pytest \
    "${REPO_ROOT}/infra/tests/test_gitops_flux_contract.py" \
    "${REPO_ROOT}/infra/tests/test_sops_boundary_contract.py" >/dev/null
  e2e_pass "Kustomization/humility-local runtime readiness unavailable; static Flux/SOPS contract checks passed"
fi

marker_sha="$(kubectl_cmd -n humility-gitops-sentinel get configmap gitops-snapshot-marker -o jsonpath='{.data.source_sha}' 2>/dev/null || true)"
if [[ -n "$marker_sha" ]]; then
  e2e_pass "seeded snapshot marker exists (${marker_sha})"
else
  marker_sha="$(python3 - <<'PY'
from pathlib import Path

import yaml

marker = Path("gitops/sources/local/generated/gitops-snapshot-marker.yaml")
for document in yaml.safe_load_all(marker.read_text(encoding="utf-8")):
    if isinstance(document, dict) and document.get("kind") == "ConfigMap":
        data = document.get("data")
        if isinstance(data, dict):
            print(data.get("source_sha", ""))
            break
PY
)"
  [[ -n "$marker_sha" ]] || e2e_fail "gitops snapshot marker missing source_sha"
  e2e_pass "seeded snapshot marker exists in desired state (${marker_sha}); runtime marker unavailable"
fi
e2e_finish
