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
    rm -rf "$temp_file" >/dev/null 2>&1 || true
  done
  if [[ "$STATIC_ONLY" -eq 0 && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system delete pod init-115-cedar init-115-service-identity --ignore-not-found >/dev/null 2>&1 || true
  fi
}

expected_policy_ids_json() {
  # OPAL Cedar uploader uses the policy file's full repo-relative path as the
  # Cedar policy ID. The seeded git repo emits one .cedar file per canonical
  # entry under <generated_dir>/<id>.cedar, so the in-Cedar IDs are
  # `<generated_dir>/<id>.cedar`.
  local generated_rel="policy/cedar/channels/local/services/server-manager-api/generated/policies"
  jq -c --arg p "$generated_rel" '[.[].id | "\($p)/\(.).cedar"] | sort' "$policy_file"
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

seed_snapshot="$(mktemp -d)"
root_render="$(mktemp)"
TEMP_FILES+=("$seed_snapshot" "$root_render")
python3 "${REPO_ROOT}/infra/scripts/render-gitops-source.py" --channel local --out "$seed_snapshot" >/dev/null
POLICY_FILE="$policy_file" SNAPSHOT_ROOT="$seed_snapshot" python3 - <<'PY' || die "Seeded Cedar policy source differs from canonical policies.json"
import json
import os
from pathlib import Path

policy_file = Path(os.environ["POLICY_FILE"])
snapshot_root = Path(os.environ["SNAPSHOT_ROOT"])
generated_dir = snapshot_root / "policy/cedar/channels/local/services/server-manager-api/generated/policies"
canonical = {
    policy["id"]: policy["content"] + "\n"
    for policy in json.loads(policy_file.read_text(encoding="utf-8"))
}
seeded = {
    path.stem: path.read_text(encoding="utf-8")
    for path in sorted(generated_dir.glob("*.cedar"))
}
if seeded != canonical:
    raise SystemExit(1)
PY
pass "Cedar policy bundle reconciles through seeded policy files"

kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$root_render"
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
python3 - <<PY || die "legacy Cedar direct writer resources still rendered"
import yaml
from pathlib import Path
for doc in yaml.safe_load_all(Path("$root_render").read_text()):
    if not isinstance(doc, dict):
        continue
    kind = doc.get("kind")
    name = doc.get("metadata", {}).get("name")
    if (kind, name) in {
        ("Job", "cedar-access-policy-" + "bootstrap"),
        ("ConfigMap", "cedar-access-policy-" + "bundle"),
    }:
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

kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system rollout status deployment/opal-client --timeout=180s >/dev/null
expected_policy_ids="$(expected_policy_ids_json)"
pass "OPAL/Cedar deployment available"

allow_payload="$(jq -nc '{principal: "User::\"sample@local.humility.local\"", action: "Action::\"api:read\"", resource: "Resource::\"server-manager-api\""}')"
deny_payload="$(jq -nc '{principal: "User::\"other@local.humility.local\"", action: "Action::\"api:read\"", resource: "Resource::\"server-manager-api\""}')"
PUBLIC_ALLOW_PAYLOAD="$(jq -nc '{
  principal: "Public::\"web-intake.local\"",
  action: "Action::\"application:submit_public\"",
  resource: "Resource::\"server-manager-api:public-applications\""
}')"
PUBLIC_DENY_PAYLOAD="$(jq -nc '{
  principal: "Public::\"web-intake.local\"",
  action: "Action::\"api:read\"",
  resource: "Resource::\"server-manager-api\""
}')"
cedar_proof_command='
set -e
policy_url="http://opal-client:8180/v1/policies"
expected="$(printf "%s" "$EXPECTED_POLICY_IDS" | tr -d "[]\"" | tr "," " ")"
wait_for_policy_ids() {
  last_body=""
  missing="$expected"
  for _ in $(seq 1 120); do
    body="$(curl -fsS "$policy_url" 2>/dev/null || true)"
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
        return 0
      fi
    fi
    sleep 1
  done
  printf "missing policy IDs:%s from http://opal-client:8180/v1/policies\nlast policies: %s\n" "$missing" "$last_body" >&2
  return 1
}
wait_for_policy_ids
allow="$(printf "%s" "$ALLOW_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
deny="$(printf "%s" "$DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
public_submit="$(printf "%s" "$PUBLIC_ALLOW_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
public_read="$(printf "%s" "$PUBLIC_DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
sleep 31
wait_for_policy_ids
allow_after_poll="$(printf "%s" "$ALLOW_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
deny_after_poll="$(printf "%s" "$DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
public_submit_after_poll="$(printf "%s" "$PUBLIC_ALLOW_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
public_read_after_poll="$(printf "%s" "$PUBLIC_DENY_PAYLOAD" | curl -fsS -X POST -H "Content-Type: application/json" --data-binary @- http://opal-client:8180/v1/is_authorized)"
printf "allow=%s\n" "$allow"
printf "deny=%s\n" "$deny"
printf "public_submit=%s\n" "$public_submit"
printf "public_read=%s\n" "$public_read"
printf "allow_after_poll=%s\n" "$allow_after_poll"
printf "deny_after_poll=%s\n" "$deny_after_poll"
printf "public_submit_after_poll=%s\n" "$public_submit_after_poll"
printf "public_read_after_poll=%s\n" "$public_read_after_poll"
'
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system delete pod init-115-cedar --ignore-not-found >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system run init-115-cedar \
  --restart=Never \
  --labels=app.kubernetes.io/name=opal-cedar,platform.humility.gg/init=115 \
  --image=curlimages/curl:8.19.0 \
  --env="EXPECTED_POLICY_IDS=${expected_policy_ids}" \
  --env="ALLOW_PAYLOAD=${allow_payload}" \
  --env="DENY_PAYLOAD=${deny_payload}" \
  --env="PUBLIC_ALLOW_PAYLOAD=${PUBLIC_ALLOW_PAYLOAD}" \
  --env="PUBLIC_DENY_PAYLOAD=${PUBLIC_DENY_PAYLOAD}" \
  --command -- /bin/sh -ec "$cedar_proof_command" >/dev/null
if ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system wait pod/init-115-cedar --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null; then
  phase="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system get pod/init-115-cedar -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system logs pod/init-115-cedar >&2 || true
  die "Cedar access policy proof pod did not succeed; phase=${phase:-unknown}"
fi
cedar_logs="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system logs pod/init-115-cedar)"
allow_count="$(grep -c '^allow=' <<<"$cedar_logs" || true)"
deny_count="$(grep -c '^deny=' <<<"$cedar_logs" || true)"
public_submit_count="$(grep -c '^public_submit=' <<<"$cedar_logs" || true)"
public_read_count="$(grep -c '^public_read=' <<<"$cedar_logs" || true)"
public_submit_after_poll_count="$(grep -c '^public_submit_after_poll=' <<<"$cedar_logs" || true)"
public_read_after_poll_count="$(grep -c '^public_read_after_poll=' <<<"$cedar_logs" || true)"
[[ "$allow_count" == "1" ]] || die "expected exactly one Cedar Allow log line, found ${allow_count}"
[[ "$deny_count" == "1" ]] || die "expected exactly one Cedar Deny log line, found ${deny_count}"
[[ "$public_submit_count" == "1" ]] || die "expected exactly one Cedar public submit Allow log line, found ${public_submit_count}"
[[ "$public_read_count" == "1" ]] || die "expected exactly one Cedar public read Deny log line, found ${public_read_count}"
[[ "$public_submit_after_poll_count" == "1" ]] || die "expected exactly one Cedar public submit Allow log line (after polling-interval recheck), found ${public_submit_after_poll_count}"
[[ "$public_read_after_poll_count" == "1" ]] || die "expected exactly one Cedar public read Deny log line (after polling-interval recheck), found ${public_read_after_poll_count}"
allowed_body="$(grep '^allow=' <<<"$cedar_logs")"
denied_body="$(grep '^deny=' <<<"$cedar_logs")"
public_submit_body="$(grep '^public_submit=' <<<"$cedar_logs")"
public_read_body="$(grep '^public_read=' <<<"$cedar_logs")"
public_submit_after_poll_body="$(grep '^public_submit_after_poll=' <<<"$cedar_logs")"
public_read_after_poll_body="$(grep '^public_read_after_poll=' <<<"$cedar_logs")"
[[ -n "$allowed_body" ]] || die "Cedar Allow decision for sample user not found"
[[ -n "$denied_body" ]] || die "Cedar Deny decision for non-sample user not found"
jq -e '.decision == "Allow"' <<<"${allowed_body#allow=}" >/dev/null || die "Cedar Allow decision for sample user not found"
jq -e '.decision == "Deny"' <<<"${denied_body#deny=}" >/dev/null || die "Cedar Deny decision for non-sample user not found"
jq -e '.decision == "Allow"' <<<"${public_submit_body#public_submit=}" >/dev/null || die "Cedar public submit runtime probe expected Allow for Public::\"web-intake.local\" application:submit_public on Resource::\"server-manager-api:public-applications\", got: ${public_submit_body#public_submit=}"
jq -e '.decision == "Deny"' <<<"${public_read_body#public_read=}" >/dev/null || die "Cedar public read runtime probe expected Deny for Public::\"web-intake.local\" api:read on Resource::\"server-manager-api\", got: ${public_read_body#public_read=}"
jq -e '.decision == "Allow"' <<<"${public_submit_after_poll_body#public_submit_after_poll=}" >/dev/null || die "Cedar public submit runtime probe expected Allow for Public::\"web-intake.local\" application:submit_public on Resource::\"server-manager-api:public-applications\" (after polling-interval recheck), got: ${public_submit_after_poll_body#public_submit_after_poll=}"
jq -e '.decision == "Deny"' <<<"${public_read_after_poll_body#public_read_after_poll=}" >/dev/null || die "Cedar public read runtime probe expected Deny for Public::\"web-intake.local\" api:read on Resource::\"server-manager-api\" (after polling-interval recheck), got: ${public_read_after_poll_body#public_read_after_poll=}"
pass "Cedar access policy enforces user rule"
pass "Cedar access policy enforces public intake rule"

"${REPO_ROOT}/infra/scripts/verify-service-identity-claim.sh" --channel "$channel" --kubeconfig "$KUBECONFIG_PATH" >/dev/null
pass "Cedar service identity claim runtime proof"

finish
