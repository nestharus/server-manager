#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
source "${REPO_ROOT}/infra/tests/fixtures/infisical/runtime-secret-contract.env"
e2e_init "04-infisical-runtime" "Infisical runtime secret sync"

require_command python3
require_command rg
for secret_path in "${REPO_ROOT}/gitops/bootstrap" "${REPO_ROOT}/gitops/channels/local/infisical"; do
  [[ -e "$secret_path" ]] || e2e_fail "GitOps secret path missing: ${secret_path#${REPO_ROOT}/}"
done
if rg -q --fixed-strings "$INFISICAL_EXPECTED_VALUE" "${REPO_ROOT}/gitops/bootstrap" "${REPO_ROOT}/gitops/channels/local/infisical"; then
  e2e_fail "Infisical fixture plaintext value is committed under GitOps secret paths"
fi
e2e_pass "Infisical plaintext fixture value is absent from GitOps secret paths"

require_cluster
kubectl_cmd -n "$INFISICAL_SYSTEM_NAMESPACE" rollout status "deployment/${INFISICAL_SERVER_DEPLOYMENT}" --timeout=300s >/dev/null
kubectl_cmd -n "$INFISICAL_SYSTEM_NAMESPACE" rollout status "deployment/${INFISICAL_OPERATOR_DEPLOYMENT}" --timeout=300s >/dev/null
e2e_pass "Infisical server and operator Deployments Available"

json_condition_true "$INFISICAL_RUNTIME_NAMESPACE" "$INFISICAL_SECRET_RESOURCE" "$INFISICAL_READY_CONDITION" \
  || e2e_fail "${INFISICAL_SECRET_RESOURCE} not ReadyToSyncSecrets=True"
e2e_pass "sample InfisicalSecret ReadyToSyncSecrets=True"

infisical_secret_json="$(kubectl_cmd -n "$INFISICAL_RUNTIME_NAMESPACE" get "$INFISICAL_SECRET_RESOURCE" -o json)"
INFISICAL_SECRET_JSON="$infisical_secret_json" python3 - "$INFISICAL_APPROVED_SCOPE_TOKEN" "$INFISICAL_TARGET_SECRET" "$INFISICAL_EXPECTED_VALUE" <<'PY' \
  || e2e_fail "InfisicalSecret scope or plaintext boundary did not match fixture"
import json
import os
import sys

scope_token = sys.argv[1]
target_secret = sys.argv[2]
plaintext_value = sys.argv[3]
payload = json.loads(os.environ["INFISICAL_SECRET_JSON"])
spec = payload.get("spec", {})

if plaintext_value in json.dumps(spec, sort_keys=True):
    raise SystemExit("plaintext fixture value appears in InfisicalSecret spec")

scope_values = []

def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("_", "").replace("-", "").lower()
            if normalized in {"projectslug", "projectid", "envslug", "environment", "environmentslug", "secretspath", "path"} and isinstance(child, str):
                scope_values.append(child)
            walk(child, path + (str(key),))
    elif isinstance(value, list):
        for child in value:
            walk(child, path)

walk(spec)
serialized_spec = json.dumps(spec, sort_keys=True)
if target_secret not in serialized_spec:
    raise SystemExit("managed target Secret is not declared by InfisicalSecret")
if not scope_values:
    raise SystemExit("InfisicalSecret does not declare a project/path scope")
if not any(scope_token in item for item in scope_values):
    raise SystemExit("InfisicalSecret project/path scope is outside the approved local fixture boundary")
PY
e2e_pass "InfisicalSecret declares approved local project/path boundary without plaintext"

value="$(kubectl_cmd -n "$INFISICAL_RUNTIME_NAMESPACE" get secret "$INFISICAL_TARGET_SECRET" -o "jsonpath={.data.${INFISICAL_TARGET_KEY}}" | base64 -d)"
[[ "$value" == "$INFISICAL_EXPECTED_VALUE" ]] || e2e_fail "sample target Secret value mismatch"
e2e_pass "target Secret contains expected sample key"
e2e_finish
