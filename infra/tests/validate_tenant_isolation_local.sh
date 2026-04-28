#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
SPAWN="${REPO_ROOT}/infra/scripts/spawn_platform_channel.py"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

usage() {
  cat <<'EOF'
Usage: validate_tenant_isolation_local.sh [--kubeconfig PATH] [--static-only]

Validates INIT-116 tenant and channel isolation. Static checks cover the channel
contract, local tenant manifests, Cedar tenant principals, Infisical project
isolation, and spawn output. Runtime checks prove tenant RBAC and Cedar deny
cross-tenant access while allowing same-tenant cross-channel access.
EOF
}

pass() {
  echo "PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "FAIL: $1" >&2
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "SKIP: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

finish() {
  echo "RESULT: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
}

die() {
  fail "$*"
  finish
  exit 1
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

expected_policy_ids_json() {
  # OPAL Cedar uploader uses the policy file's full repo-relative path as the
  # Cedar policy ID — see validate_access_policy_local.sh for the same logic.
  local generated_rel="policy/cedar/channels/local/services/server-manager-api/generated/policies"
  jq -c --arg p "$generated_rel" '[.[].id | "\($p)/\(.).cedar"] | sort' "${REPO_ROOT}/policy/cedar/channels/local/services/server-manager-api/policies.json"
}

cleanup() {
  if [[ "$STATIC_ONLY" -eq 0 && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl_cmd -n auth-system delete pod init-116-cedar --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift
      ;;
    --static-only)
      STATIC_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
  shift
done

command -v jq >/dev/null 2>&1 || die "jq is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

resolved="$(python3 "$RESOLVER" --channel local)"
python3 - "$REPO_ROOT" "$resolved" <<'PY' || die "tenant isolation channel contract"
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
resolved = json.loads(sys.argv[2])
fixture = yaml.safe_load(
    (root / "infra/tests/fixtures/contracts/tenant_isolation_matrix.yml").read_text()
)
paths = fixture["contract_paths"]
tenant_isolation = resolved["tenant_isolation"]

def require(path, expected):
    cursor = tenant_isolation
    for key in path:
        assert key in cursor, f"missing tenant_isolation.{'.'.join(path)}"
        cursor = cursor[key]
    assert cursor == expected, f"tenant_isolation.{'.'.join(path)} expected {expected!r}, got {cursor!r}"

assert tenant_isolation["namespace_pattern"] == paths["namespace_pattern"]
require(("rbac", "operator_group_prefix"), paths["rbac_operator_group_prefix"])
require(
    ("network_policy", "allow_same_tenant_cross_channel"),
    paths["network_policy_allow_same_tenant_cross_channel"],
)
require(("infisical", "project_pattern"), paths["infisical_project_pattern"])
require(("storage", "s3_prefix_pattern"), paths["s3_prefix_pattern"])
require(("database", "schema_pattern"), paths["db_schema_pattern"])
PY
pass "resolved tenant isolation channel contract"

python3 - "$REPO_ROOT" <<'PY' || die "tenant manifests encode namespace, RBAC, NetworkPolicy, and Infisical isolation"
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
fixture = yaml.safe_load((root / "infra/tests/fixtures/contracts/tenant_isolation_matrix.yml").read_text())
docs = []
for path in sorted((root / "gitops/channels/local/tenants").glob("*/*.yaml")):
    if path.name == "kustomization.yaml":
        continue
    docs.extend(doc for doc in yaml.safe_load_all(path.read_text()) if isinstance(doc, dict))

by_key = {
    (doc["kind"], doc["metadata"]["name"], doc["metadata"].get("namespace")): doc
    for doc in docs
}
for tenant_spec in fixture["tenants"]:
    namespace = tenant_spec["namespace"]
    tenant = tenant_spec["tenant"]
    channel = tenant_spec["channel"]
    labels = by_key[("Namespace", namespace, None)]["metadata"]["labels"]
    assert labels["platform.humility.gg/tenant"] == tenant
    assert labels["platform.humility.gg/channel"] == channel
    assert labels["pod-security.kubernetes.io/enforce"] == "restricted"
    binding = by_key[("RoleBinding", "tenant-operators", namespace)]
    assert binding["subjects"][0]["name"] == f"humility:tenant:{tenant}:operators"
    policy = by_key[("NetworkPolicy", "allow-same-tenant-cross-channel", namespace)]
    assert policy["spec"]["egress"][0]["to"][0]["namespaceSelector"]["matchLabels"] == {
        "platform.humility.gg/tenant": tenant
    }
    secret = by_key[("InfisicalSecret", "tenant-runtime", namespace)]
    scope = secret["spec"]["authentication"]["universalAuth"]["secretsScope"]
    assert scope["projectSlug"] == tenant_spec["infisical_project"]
    assert scope["secretsPath"] == "/runtime"
PY
pass "tenant manifests encode namespace, RBAC, NetworkPolicy, and Infisical isolation"

jq -e '
  any(.[]; .id == "local-tenant-sample-local-access") and
  any(.[]; .id == "local-tenant-sample-dev-access") and
  any(.[]; .id == "local-tenant-other-local-access") and
  (any(.[]; (.content | contains("Tenant::\"sample\"") and contains("TenantChannel::\"other:local\""))) | not)
' "${REPO_ROOT}/policy/cedar/channels/local/services/server-manager-api/policies.json" >/dev/null || die "Cedar tenant policy contract"
pass "Cedar tenant principals and resource selectors are scoped"

spawn_dir="${REPO_ROOT}/.tmp/validate-tenant-spawn"
rm -rf "$spawn_dir"
python3 "$SPAWN" --parent local --suffix pr-123 --tenant sample --out "$spawn_dir" >/dev/null
[[ -f "$spawn_dir/channel.yaml" ]] || die "spawn wrote channel.yaml"
[[ -f "$spawn_dir/tenant-resources/sample-local-pr-123/namespace.yaml" ]] || die "spawn wrote tenant namespace"
grep -q 'projectSlug: tenant-sample-local-pr-123' "$spawn_dir/tenant-resources/sample-local-pr-123/infisicalsecret.yaml" || die "spawn wrote tenant Infisical project"
pass "spawn flow writes tenant-scoped resources"

if command -v kubectl >/dev/null 2>&1; then
  kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >/dev/null
  pass "local root renders tenant isolation resources"
else
  skip "kubectl kustomize skipped; kubectl not installed"
fi

if [[ "$STATIC_ONLY" -eq 1 ]]; then
  skip "runtime tenant proof skipped by --static-only"
  finish
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

for namespace in sample-local sample-dev other-local; do
  kubectl_cmd get namespace "$namespace" >/dev/null
done
pass "sample and cross-tenant proof namespaces exist"

sample_local="$(kubectl_cmd auth can-i get pods -n sample-local --as=tenant-sample --as-group=humility:tenant:sample:operators)"
sample_dev="$(kubectl_cmd auth can-i get pods -n sample-dev --as=tenant-sample --as-group=humility:tenant:sample:operators)"
sample_other="$(kubectl_cmd auth can-i get pods -n other-local --as=tenant-sample --as-group=humility:tenant:sample:operators || true)"
other_sample="$(kubectl_cmd auth can-i get pods -n sample-local --as=tenant-other --as-group=humility:tenant:other:operators || true)"
[[ "$sample_local" == "yes" ]] || die "sample tenant cannot access sample-local"
[[ "$sample_dev" == "yes" ]] || die "sample tenant cannot access sample-dev"
[[ "$sample_other" == "no" ]] || die "sample tenant can access other-local"
[[ "$other_sample" == "no" ]] || die "other tenant can access sample-local"
pass "tenant RBAC allows same tenant channels and denies cross-tenant access"

kubectl_cmd -n auth-system rollout status deployment/opal-client --timeout=180s >/dev/null
expected_policy_ids="$(expected_policy_ids_json)"
allow_local_payload="$(jq -nc '{principal: "Tenant::\"sample\"", action: "Action::\"tenant:channel:access\"", resource: "TenantChannel::\"sample:local\""}')"
allow_dev_payload="$(jq -nc '{principal: "Tenant::\"sample\"", action: "Action::\"tenant:channel:access\"", resource: "TenantChannel::\"sample:dev\""}')"
deny_payload="$(jq -nc '{principal: "Tenant::\"sample\"", action: "Action::\"tenant:channel:access\"", resource: "TenantChannel::\"other:local\""}')"
cedar_proof_command='
set -e
expected="$(printf "%s" "$EXPECTED_POLICY_IDS" | tr -d "[]\"" | tr "," " ")"
last_body=""
missing="$expected"
for _ in $(seq 1 120); do
  body="$(curl -fsS http://opal-client:8180/v1/policies 2>/dev/null || true)"
  last_body="$body"
  missing=""
  if [ -n "$body" ]; then
    for id in $expected; do
      if ! printf "%s" "$body" | grep -Eq "\"id\"[[:space:]]*:[[:space:]]*\"${id}\""; then
        missing="${missing} ${id}"
      fi
    done
    if [ -z "$missing" ]; then
      printf "policy IDs hydrated: %s\n" "$expected"
      break
    fi
  fi
  sleep 1
done
if [ -n "$missing" ]; then
  printf "missing policy IDs:%s\nlast policies: %s\n" "$missing" "$last_body" >&2
  exit 1
fi
allow_local="$(printf "%s" "$ALLOW_LOCAL_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
allow_dev="$(printf "%s" "$ALLOW_DEV_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
deny="$(printf "%s" "$DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
printf "allow_local=%s\n" "$allow_local"
printf "allow_dev=%s\n" "$allow_dev"
printf "deny=%s\n" "$deny"
'
kubectl_cmd -n auth-system delete pod init-116-cedar --ignore-not-found >/dev/null
kubectl_cmd -n auth-system run init-116-cedar \
  --restart=Never \
  --labels=app.kubernetes.io/name=opal-cedar,platform.humility.gg/init=116 \
  --image=curlimages/curl:8.19.0 \
  --env="EXPECTED_POLICY_IDS=${expected_policy_ids}" \
  --env="ALLOW_LOCAL_PAYLOAD=${allow_local_payload}" \
  --env="ALLOW_DEV_PAYLOAD=${allow_dev_payload}" \
  --env="DENY_PAYLOAD=${deny_payload}" \
  --command -- /bin/sh -ec "$cedar_proof_command" >/dev/null
if ! kubectl_cmd -n auth-system wait pod/init-116-cedar --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null; then
  kubectl_cmd -n auth-system logs pod/init-116-cedar >&2 || true
  die "Cedar tenant proof pod did not succeed"
fi
cedar_logs="$(kubectl_cmd -n auth-system logs pod/init-116-cedar)"
jq -e '.decision == "Allow"' <<<"$(grep '^allow_local=' <<<"$cedar_logs" | sed 's/^allow_local=//')" >/dev/null || die "Cedar did not allow sample-local"
jq -e '.decision == "Allow"' <<<"$(grep '^allow_dev=' <<<"$cedar_logs" | sed 's/^allow_dev=//')" >/dev/null || die "Cedar did not allow sample-dev"
jq -e '.decision == "Deny"' <<<"$(grep '^deny=' <<<"$cedar_logs" | sed 's/^deny=//')" >/dev/null || die "Cedar did not deny cross-tenant resource"
pass "Cedar tenant proof allows same tenant channels and denies cross-tenant access"

finish
