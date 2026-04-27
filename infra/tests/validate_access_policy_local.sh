#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: validate_access_policy_local.sh [--channel local] [--kubeconfig PATH] [--static-only]

Validates INIT-115 access policy, service identity, rotation, break-glass,
object-storage policy, and operator RBAC contracts. Runtime proof checks that
the reconciled Cedar bundle allows the sample user and Buildkite service
identity while denying a non-sample user.
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

cleanup() {
  local temp_file
  for temp_file in "${TEMP_FILES[@]:-}"; do
    rm -f "$temp_file" >/dev/null 2>&1 || true
  done
  if [[ "$STATIC_ONLY" -eq 0 && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system delete pod init-115-cedar init-115-service-identity --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || die "--channel requires a value"
      CHANNEL_REQUEST="$2"
      shift
      ;;
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

resolved="$(python3 "$RESOLVER" --channel "$CHANNEL_REQUEST")"
channel="$(jq -er '.id' <<<"$resolved")"
bundle_path="$(jq -er '.access_policy.services.server_manager_api.bundle_path' <<<"$resolved")"
policy_file="${REPO_ROOT}/${bundle_path}/policies.json"
identity_file="${REPO_ROOT}/${bundle_path}/service-identities.json"

[[ "$channel" == "local" ]] || die "expected local channel, got ${channel}"
pass "resolved access_policy channel contract"

[[ -f "$policy_file" ]] || die "missing policy file: ${policy_file}"
[[ -f "$identity_file" ]] || die "missing service identity file: ${identity_file}"
jq -e 'length >= 3' "$policy_file" >/dev/null || die "expected at least three Cedar policies"
jq -e '.identities.buildkite_agent.cedar_principal == "Service::\"buildkite-agent.local\""' "$identity_file" >/dev/null || die "Buildkite identity contract"
pass "structured Cedar policy bundle exists per channel and service"

config_policy="$(mktemp)"
root_render="$(mktemp)"
TEMP_FILES+=("$config_policy" "$root_render")
CONFIGMAP_PATH="${REPO_ROOT}/gitops/channels/local/auth/opal-cedar/access-policy-configmap.yaml" python3 - <<'PY' >"$config_policy"
import os
import yaml
from pathlib import Path
doc = yaml.safe_load(Path(os.environ["CONFIGMAP_PATH"]).read_text())
print(doc["data"]["policies.json"])
PY
jq -S . "$policy_file" >"${config_policy}.repo"
jq -S . "$config_policy" >"${config_policy}.gitops"
TEMP_FILES+=("${config_policy}.repo" "${config_policy}.gitops")
diff -u "${config_policy}.repo" "${config_policy}.gitops" >/dev/null || die "GitOps ConfigMap policy differs from policy repo"
pass "Cedar policy bundle reconciles through GitOps ConfigMap"

kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$root_render"
grep -q 'name: cedar-access-policy-bootstrap' "$root_render" || die "Cedar bootstrap job missing"
grep -q 'name: service-identity-issuer' "$root_render" || die "service identity issuer missing"
grep -q 'name: platform-operator-appcluster-claims' "$root_render" || die "operator claim RBAC missing"
python3 - <<PY || die "crossplane-admin ClusterRoleBinding still rendered"
import sys
import yaml
from pathlib import Path
for doc in yaml.safe_load_all(Path("$root_render").read_text()):
    if not isinstance(doc, dict):
        continue
    if doc.get("kind") == "ClusterRoleBinding" and doc.get("metadata", {}).get("name") == "crossplane-admin":
        raise SystemExit(1)
PY
pass "local root renders access policy, service identity, and narrowed operator RBAC"

"${REPO_ROOT}/infra/scripts/verify-service-identity-claim.sh" --channel "$channel" --static-only >/dev/null
pass "service identity claim dry-run verified"
"${REPO_ROOT}/infra/scripts/rotate-platform-credentials.sh" --channel "$channel" >/dev/null
pass "credential rotation dry-run verified"
"${REPO_ROOT}/infra/scripts/break-glass-sops-recovery.sh" --channel "$channel" >/dev/null
pass "break-glass recovery dry-run verified"
"${REPO_ROOT}/infra/scripts/apply-object-storage-policies.sh" --channel "$channel" >/dev/null
pass "object-storage policy dry-run verified"

if [[ "$STATIC_ONLY" -eq 1 ]]; then
  skip "runtime Cedar proof skipped by --static-only"
  finish
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system rollout status deployment/opal-client --timeout=300s >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system wait job/cedar-access-policy-bootstrap --for=condition=Complete --timeout=300s >/dev/null
pass "OPAL/Cedar available and access policy loaded"

allow_payload="$(jq -nc '{principal: "User::\"sample@local.humility.local\"", action: "Action::\"api:read\"", resource: "Resource::\"server-manager-api\""}')"
deny_payload="$(jq -nc '{principal: "User::\"other@local.humility.local\"", action: "Action::\"api:read\"", resource: "Resource::\"server-manager-api\""}')"
cedar_proof_command='
set -e
ready=0
for _ in $(seq 1 30); do
  if curl -fsS http://opal-client:8180/v1/policies >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" = 1
allow="$(printf "%s" "$ALLOW_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
deny="$(printf "%s" "$DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
printf "allow=%s\n" "$allow"
printf "deny=%s\n" "$deny"
'
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system delete pod init-115-cedar --ignore-not-found >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system run init-115-cedar \
  --restart=Never \
  --labels=app.kubernetes.io/name=opal-cedar,platform.humility.gg/init=115 \
  --image=curlimages/curl:8.19.0 \
  --env="ALLOW_PAYLOAD=${allow_payload}" \
  --env="DENY_PAYLOAD=${deny_payload}" \
  --command -- /bin/sh -ec "$cedar_proof_command" >/dev/null
if ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system wait pod/init-115-cedar --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null; then
  phase="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system get pod/init-115-cedar -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system logs pod/init-115-cedar >&2 || true
  die "Cedar access policy proof pod did not succeed; phase=${phase:-unknown}"
fi
cedar_logs="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system logs pod/init-115-cedar)"
allow_count="$(grep -c '^allow=' <<<"$cedar_logs" || true)"
deny_count="$(grep -c '^deny=' <<<"$cedar_logs" || true)"
[[ "$allow_count" == "1" ]] || die "expected exactly one Cedar Allow log line, found ${allow_count}"
[[ "$deny_count" == "1" ]] || die "expected exactly one Cedar Deny log line, found ${deny_count}"
allowed_body="$(grep '^allow=' <<<"$cedar_logs")"
denied_body="$(grep '^deny=' <<<"$cedar_logs")"
[[ -n "$allowed_body" ]] || die "Cedar Allow decision for sample user not found"
[[ -n "$denied_body" ]] || die "Cedar Deny decision for non-sample user not found"
jq -e '.decision == "Allow"' <<<"${allowed_body#allow=}" >/dev/null || die "Cedar Allow decision for sample user not found"
jq -e '.decision == "Deny"' <<<"${denied_body#deny=}" >/dev/null || die "Cedar Deny decision for non-sample user not found"
pass "Cedar access policy enforces user rule"

"${REPO_ROOT}/infra/scripts/verify-service-identity-claim.sh" --channel "$channel" --kubeconfig "$KUBECONFIG_PATH" >/dev/null
pass "Cedar service identity claim runtime proof"

finish
