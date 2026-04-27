#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "03-sops-bootstrap" "SOPS age bootstrap sentinel"

require_cluster
kubectl_cmd -n flux-system get secret sops-age -o jsonpath='{.data.age\.agekey}' | grep -q . \
  || e2e_fail "Secret/sops-age missing age.agekey"
e2e_pass "Flux SOPS age Secret exists"

kubectl_cmd -n humility-gitops-sentinel get secret bootstrap-sentinel -o jsonpath='{.data.message}' | base64 -d \
  | tee "$(e2e_log_path bootstrap-sentinel)" | grep -q "humility-local-sops-ready" \
  || e2e_fail "bootstrap-sentinel Secret did not decrypt to expected value"
e2e_pass "encrypted sentinel reconciled and decrypted"
e2e_finish
