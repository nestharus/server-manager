#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
KUBECONFIG_ARG=()
KEY_FILE=""
EXECUTE=0

usage() {
  cat <<'EOF'
Usage: break-glass-sops-recovery.sh [--channel local] [--key-file PATH] [--kubeconfig PATH] [--execute]

Dry-run by default. The execute path re-encrypts the SOPS sentinel from the
operator-local age key and asks Flux to reconcile the channel kustomization.
Use this when Infisical is unavailable but Flux must regain decryption.
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
    --key-file)
      [[ $# -ge 2 ]] || die "--key-file requires a value"
      KEY_FILE="$2"
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

command -v jq >/dev/null 2>&1 || die "jq is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

resolved="$(python3 "$RESOLVER" --channel "$CHANNEL_REQUEST")"
channel="$(jq -er '.id' <<<"$resolved")"
sentinel="$(jq -er '.access_policy.break_glass.sentinel_path' <<<"$resolved")"
flux_kustomization="$(jq -er '.access_policy.break_glass.flux_kustomization' <<<"$resolved")"
flux_namespace="$(jq -er '.access_policy.break_glass.flux_namespace' <<<"$resolved")"
secret_name="$(jq -er '.gitops.sops_age_secret_name' <<<"$resolved")"
secret_namespace="$(jq -er '.gitops.decryption_secret_namespace' <<<"$resolved")"

if [[ -z "$KEY_FILE" ]]; then
  KEY_FILE="${HOME}/.config/sops/age/${channel}.txt"
fi

[[ -f "${REPO_ROOT}/${sentinel}" ]] || die "sentinel not found: ${sentinel}"

if [[ "$EXECUTE" -eq 0 ]]; then
  echo "PASS: break-glass dry-run resolved channel ${channel}"
  echo "PLAN: use ${KEY_FILE} to re-encrypt ${sentinel}"
  echo "PLAN: apply Secret/${secret_name} in namespace ${secret_namespace}"
  echo "PLAN: reconcile Flux Kustomization/${flux_kustomization} in namespace ${flux_namespace}"
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
command -v sops >/dev/null 2>&1 || die "sops is required"
command -v flux >/dev/null 2>&1 || die "flux is required"
[[ -f "$KEY_FILE" ]] || die "age key file not found: ${KEY_FILE}"

tmp_sentinel=""
tmp_encrypted=""
cleanup() {
  rm -f "${tmp_sentinel:-}" "${tmp_encrypted:-}"
  rmdir "${REPO_ROOT}/.tmp" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "${REPO_ROOT}/.tmp"
tmp_sentinel="$(mktemp)"
tmp_encrypted="$(mktemp "${REPO_ROOT}/.tmp/sops-sentinel.enc.XXXXXX")"

cat >"$tmp_sentinel" <<YAML
apiVersion: v1
kind: Secret
metadata:
  name: sops-sentinel
  namespace: ${flux_namespace}
  labels:
    channel: ${channel}
    sentinel: sops-${channel}-ready
type: Opaque
stringData:
  ready: "true"
YAML

echo "EXEC: re-encrypting ${tmp_sentinel} for ${sentinel} to temporary file ${tmp_encrypted}"
SOPS_AGE_KEY_FILE="$KEY_FILE" sops --encrypt \
  --filename-override "$sentinel" \
  "$tmp_sentinel" >"$tmp_encrypted"
echo "EXEC: moving re-encrypted sentinel into ${sentinel}"
mv "$tmp_encrypted" "${REPO_ROOT}/${sentinel}"
tmp_encrypted=""

echo "EXEC: applying Secret/${secret_name} in namespace ${secret_namespace}"
kubectl ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} -n "$secret_namespace" create secret generic "$secret_name" \
  --from-file=age.agekey="$KEY_FILE" \
  --dry-run=client \
  -o yaml | kubectl ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} apply -f -
echo "EXEC: reconciling Flux Kustomization/${flux_kustomization} in namespace ${flux_namespace}"
flux ${KUBECONFIG_ARG[@]+"${KUBECONFIG_ARG[@]}"} -n "$flux_namespace" reconcile kustomization "$flux_kustomization" --with-source
echo "PASS: break-glass SOPS recovery executed for ${channel}"
