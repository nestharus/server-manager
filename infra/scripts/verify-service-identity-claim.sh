#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
AUTH_NAMESPACE="auth-system"

usage() {
  cat <<'EOF'
Usage: verify-service-identity-claim.sh [--channel local] [--kubeconfig PATH] [--static-only]

Verifies the INIT-115 service identity claim contract. Static mode checks the
channel contract and Cedar bundle. Runtime mode additionally asks the local
OPAL/Cedar client to authorize the Buildkite service identity claim.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

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
    --static-only|--dry-run)
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
principal="$(jq -er '.access_policy.service_identity.identities.buildkite_agent.cedar_principal' <<<"$resolved")"
subject="$(jq -er '.access_policy.service_identity.identities.buildkite_agent.subject' <<<"$resolved")"
audience="$(jq -er '.access_policy.service_identity.audience' <<<"$resolved")"
issuer="$(jq -er '.access_policy.service_identity.issuer' <<<"$resolved")"
policy_file="${REPO_ROOT}/${bundle_path}/policies.json"
identity_file="${REPO_ROOT}/${bundle_path}/service-identities.json"

[[ -f "$policy_file" ]] || die "missing policy file: ${policy_file}"
[[ -f "$identity_file" ]] || die "missing service identity file: ${identity_file}"

jq -e --arg principal "$principal" '.[] | select(.content | contains($principal))' "$policy_file" >/dev/null \
  || die "Cedar bundle does not reference ${principal}"
jq -e --arg subject "$subject" --arg principal "$principal" --arg audience "$audience" --arg issuer "$issuer" '
  .issuer == $issuer
  and .audience == $audience
  and .identities.buildkite_agent.subject == $subject
  and .identities.buildkite_agent.cedar_principal == $principal
' "$identity_file" >/dev/null || die "service identity claim file does not match channel contract"

echo "PASS: ${channel} service identity claim maps ${subject} to ${principal}"
payload="$(jq -nc --arg principal "$principal" \
  '{principal: $principal, action: "Action::\"api:ci:deploy\"", resource: "Resource::\"server-manager-api\""}')"
proof_command='
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
printf "%s" "$AUTH_PAYLOAD" |
  curl -fsS -X POST \
    -H "Content-Type: application/json" \
    --data-binary @- \
    http://opal-client:8180/v1/is_authorized
'

if [[ "$STATIC_ONLY" -eq 1 ]]; then
  echo "PASS: static service identity verification complete"
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" wait job/cedar-access-policy-bootstrap --for=condition=Complete --timeout=300s >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" delete pod init-115-service-identity --ignore-not-found >/dev/null
cleanup_pod() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" delete pod init-115-service-identity --ignore-not-found >/dev/null 2>&1 || true
}
trap cleanup_pod EXIT
kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" run init-115-service-identity \
  --restart=Never \
  --labels=app.kubernetes.io/name=opal-cedar,platform.humility.gg/init=115 \
  --image=curlimages/curl:8.19.0 \
  --env="AUTH_PAYLOAD=${payload}" \
  --command -- /bin/sh -ec "$proof_command" >/dev/null
if ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" wait pod/init-115-service-identity --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null; then
  phase="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" get pod/init-115-service-identity -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" logs pod/init-115-service-identity >&2 || true
  die "service identity proof pod did not succeed; phase=${phase:-unknown}"
fi
body="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" logs pod/init-115-service-identity)"
jq -e '.decision == "Allow"' <<<"$body" >/dev/null || die "Cedar did not allow Buildkite service identity"
cleanup_pod
trap - EXIT
echo "PASS: runtime Cedar service identity claim allowed"
