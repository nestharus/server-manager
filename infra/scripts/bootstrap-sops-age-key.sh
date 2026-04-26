#!/usr/bin/env bash
set -euo pipefail

CHANNEL_ID="local"
KEY_FILE="${HOME}/.config/sops/age/local.txt"
KUBECONFIG_ARG=()
SECRET_NAMESPACE="flux-system"
SECRET_NAME="sops-age"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage: bootstrap-sops-age-key.sh [--channel local] [--key-file path] [--kubeconfig path]

Creates or reuses the operator-local age private key and applies it to the
cluster as Secret/sops-age in namespace flux-system.

Options:
  --channel <id>     Channel id for the default key path (default: local)
  --key-file <path>  Override age private key path
  --kubeconfig <p>   Pass a kubeconfig path to kubectl
  --namespace <n>    Secret namespace (default: flux-system)
  --secret-name <n>  Secret name (default: sops-age)
  -h, --help         Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_ID="$2"
        KEY_FILE="${HOME}/.config/sops/age/${CHANNEL_ID}.txt"
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
      --namespace)
        [[ $# -ge 2 ]] || die "--namespace requires a value"
        SECRET_NAMESPACE="$2"
        shift
        ;;
      --secret-name)
        [[ $# -ge 2 ]] || die "--secret-name requires a value"
        SECRET_NAME="$2"
        shift
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
}

public_key() {
  awk '/^# public key: / { print $4; found = 1; exit } END { exit found ? 0 : 1 }' "$KEY_FILE"
}

parse_args "$@"

command -v age-keygen >/dev/null 2>&1 || die "age-keygen is required"
command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

mkdir -p "$(dirname "$KEY_FILE")"
if [[ ! -f "$KEY_FILE" ]]; then
  tmp_dir="$(mktemp -d)"
  tmp_key="${tmp_dir}/local.txt"
  age-keygen -o "$tmp_key" >/dev/null
  chmod 600 "$tmp_key"
  mv "$tmp_key" "$KEY_FILE"
  rmdir "$tmp_dir"
  echo "Generated age private key: ${KEY_FILE}"
else
  chmod 600 "$KEY_FILE"
  echo "Using existing age private key: ${KEY_FILE}"
fi

recipient="$(public_key)" || die "could not read public recipient from ${KEY_FILE}"

manifest_dir="${REPO_ROOT}/.tmp/sops-age-secret"
manifest_path="${manifest_dir}/${CHANNEL_ID}.yaml"
mkdir -p "$manifest_dir"

kubectl "${KUBECONFIG_ARG[@]}" create secret generic "$SECRET_NAME" \
  --namespace "$SECRET_NAMESPACE" \
  --from-file=age.agekey="${KEY_FILE}" \
  --dry-run=client \
  -o yaml > "$manifest_path"

if kubectl "${KUBECONFIG_ARG[@]}" get namespace "$SECRET_NAMESPACE" >/dev/null 2>&1; then
  kubectl "${KUBECONFIG_ARG[@]}" apply -f "$manifest_path"
else
  echo "Cluster namespace ${SECRET_NAMESPACE} is not reachable; wrote Secret manifest: ${manifest_path}"
fi

cat <<EOF

SOPS age recipient for channel ${CHANNEL_ID}:
${recipient}

Replace the placeholder recipient in .sops.yaml with this value, then re-encrypt
the bootstrap sentinel from its plaintext contract:

  tmp_sentinel="\$(mktemp)"
  cat > "\${tmp_sentinel}" <<'YAML'
apiVersion: v1
kind: Secret
metadata:
  name: sops-sentinel
  namespace: flux-system
  labels:
    channel: local
    sentinel: sops-local-ready
type: Opaque
stringData:
  ready: "true"
YAML
  sops --encrypt --filename-override gitops/bootstrap/sops-sentinel.enc.yaml "\${tmp_sentinel}" > gitops/bootstrap/sops-sentinel.enc.yaml
  rm -f "\${tmp_sentinel}"

The private key stays outside the repo. Flux reads the in-cluster Secret/sops-age.
EOF
