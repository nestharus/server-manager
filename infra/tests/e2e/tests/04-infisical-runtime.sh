#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "04-infisical-runtime" "Infisical runtime secret sync"

require_cluster
kubectl_cmd -n infisical-system rollout status deployment/infisical-infisical-standalone-infisical --timeout=300s >/dev/null
kubectl_cmd -n infisical-system rollout status deployment/infisical-opera-controller-manager --timeout=300s >/dev/null
e2e_pass "Infisical server and operator Deployments Available"

json_condition_true infisical-sample infisicalsecret/infisical-local-sample secrets.infisical.com/ReadyToSyncSecrets \
  || e2e_fail "InfisicalSecret/infisical-local-sample not ReadyToSyncSecrets=True"
e2e_pass "sample InfisicalSecret ReadyToSyncSecrets=True"

value="$(kubectl_cmd -n infisical-sample get secret infisical-local-sample -o jsonpath='{.data.INFISICAL_SAMPLE_KEY}' | base64 -d)"
[[ "$value" == "infisical-local-ready" ]] || e2e_fail "sample target Secret value mismatch"
e2e_pass "target Secret contains expected sample key"
e2e_finish
