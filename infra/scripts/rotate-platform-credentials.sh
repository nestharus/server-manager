#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
MODE="all"
EXECUTE=0
KUBECONFIG_ARG=()

usage() {
  cat <<'EOF'
Usage: rotate-platform-credentials.sh [--channel local] [--mode all|infisical-ua|sops-age|sops-recipients] [--kubeconfig PATH] [--execute]

Dry-run by default. Execution is intentionally narrow:
  - infisical-ua: replace Secret/infisical-operator-auth from supplied env vars
  - sops-age: call bootstrap-sops-age-key.sh with a new key file path
  - sops-recipients: verify .sops.yaml and re-encrypt the bootstrap sentinel

Required execute guard:
  ROTATION_CONFIRM=<channel>/<mode>
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
    --mode)
      [[ $# -ge 2 ]] || die "--mode requires a value"
      MODE="$2"
      shift
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_ARG=(--kubeconfig "$2")
      shift
      ;;
    --execute)
      EXECUTE=1
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

case "$MODE" in
  all|infisical-ua|sops-age|sops-recipients) ;;
  *) die "invalid mode: ${MODE}" ;;
esac

command -v jq >/dev/null 2>&1 || die "jq is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

resolved="$(python3 "$RESOLVER" --channel "$CHANNEL_REQUEST")"
channel="$(jq -er '.id' <<<"$resolved")"
ua_secret="$(jq -er '.infisical.universal_auth_secret_name' <<<"$resolved")"
ua_namespace="$(jq -er '.infisical.universal_auth_secret_namespace' <<<"$resolved")"
cadence="$(jq -c '.access_policy.credential_rotation.cadence_days' <<<"$resolved")"
paths="$(jq -r '.access_policy.credential_rotation.infisical_paths[]' <<<"$resolved")"

if [[ "$EXECUTE" -eq 0 ]]; then
  echo "PASS: credential rotation dry-run resolved channel ${channel}"
  echo "CADENCE: ${cadence}"
  while IFS= read -r path; do
    echo "PLAN: rotate or verify Infisical path ${path}"
  done <<<"$paths"
  echo "PLAN: rotate ${ua_namespace}/Secret/${ua_secret} for Infisical Universal Auth"
  echo "PLAN: rotate SOPS age key and recipients through bootstrap sentinel re-encryption"
  exit 0
fi

[[ "${ROTATION_CONFIRM:-}" == "${channel}/${MODE}" ]] || die "set ROTATION_CONFIRM=${channel}/${MODE}"
command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

if [[ "$MODE" == "all" || "$MODE" == "infisical-ua" ]]; then
  : "${INFISICAL_UA_CLIENT_ID:?required}"
  : "${INFISICAL_UA_CLIENT_SECRET:?required}"
  : "${INFISICAL_ORGANIZATION_ID:?required}"
  kubectl ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} -n "$ua_namespace" create secret generic "$ua_secret" \
    --from-literal=clientId="$INFISICAL_UA_CLIENT_ID" \
    --from-literal=clientSecret="$INFISICAL_UA_CLIENT_SECRET" \
    --from-literal=organizationId="$INFISICAL_ORGANIZATION_ID" \
    --dry-run=client \
    -o yaml | kubectl ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} apply -f -
  echo "PASS: Infisical Universal Auth Secret rotated"
fi

if [[ "$MODE" == "all" || "$MODE" == "sops-age" ]]; then
  new_key="${SOPS_AGE_KEY_FILE:-${HOME}/.config/sops/age/${channel}-$(date +%Y%m%d).txt}"
  "${REPO_ROOT}/infra/scripts/bootstrap-sops-age-key.sh" --channel "$channel" --key-file "$new_key" ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"}
  echo "PASS: SOPS age key rotation bootstrap completed"
fi

if [[ "$MODE" == "all" || "$MODE" == "sops-recipients" ]]; then
  "${REPO_ROOT}/infra/scripts/break-glass-sops-recovery.sh" --channel "$channel" ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} --execute
  echo "PASS: SOPS recipient sentinel re-encryption completed"
fi
