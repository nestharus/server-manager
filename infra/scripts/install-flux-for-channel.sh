#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
RENDERER="${REPO_ROOT}/infra/scripts/render-gitops-source.py"
AGE_BOOTSTRAP="${REPO_ROOT}/infra/scripts/bootstrap-sops-age-key.sh"
INFISICAL_BOOTSTRAP="${REPO_ROOT}/infra/scripts/bootstrap-infisical-identity.sh"
CHANNEL_ID="local"
WAIT_TIMEOUT="180s"
INFISICAL_WAIT_TIMEOUT="300s"
INFISICAL_NAMESPACE="infisical-system"
INFISICAL_SERVER_DEPLOYMENT="infisical-infisical-standalone-infisical"
INFISICAL_POSTGRES_STATEFULSET="postgresql"
INFISICAL_REDIS_STATEFULSET="redis-master"
INFISICAL_OPERATOR_DEPLOYMENT="infisical-opera-controller-manager"
INFISICAL_SAMPLE_NAMESPACE="infisical-sample"
INFISICAL_SAMPLE_NAME="infisical-local-sample"
INFISICAL_SAMPLE_KEY="INFISICAL_SAMPLE_KEY"
INFISICAL_SAMPLE_VALUE="infisical-local-ready"

usage() {
  cat <<'EOF'
Usage: install-flux-for-channel.sh [--channel local]

Installs Flux into the local k3d channel, seeds the in-cluster Git daemon,
delivers the SOPS age key Secret, applies Flux source CRs, and waits for
reconciliation.

Options:
  --channel <id>  Channel id to resolve (default: local)
  -h, --help      Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_ID="$2"
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

json_field() {
  local field="$1"

  "$PYTHON_BIN" - "$RESOLVED_JSON" "$field" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
field = sys.argv[2]
gitops = data.get("gitops", {})

if field == "target":
    print(data["cluster"]["target"])
elif field == "kubeconfig_path":
    print(data["cluster"].get("kubeconfig_path") or f"~/.kube/humility-{data['id']}.yaml")
elif field == "source_name":
    print(gitops["kustomization_name"])
elif field == "source_namespace":
    print(gitops["kustomization_namespace"])
elif field == "sops_age_secret_name":
    print(gitops["sops_age_secret_name"])
elif field == "decryption_secret_namespace":
    print(gitops["decryption_secret_namespace"])
elif field == "infisical_operator_namespace":
    print(data["infisical"]["operator_namespace"])
elif field == "infisical_universal_auth_secret_name":
    print(data["infisical"]["universal_auth_secret_name"])
elif field == "infisical_universal_auth_secret_namespace":
    print(data["infisical"]["universal_auth_secret_namespace"])
else:
    raise SystemExit(f"unknown field: {field}")
PY
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

flux_cmd() {
  KUBECONFIG="$KUBECONFIG_PATH" flux "$@"
}

wait_for_flux_controllers() {
  log "Waiting for Flux controllers"
  kubectl_cmd wait --for=condition=Established crd/gitrepositories.source.toolkit.fluxcd.io --timeout="$WAIT_TIMEOUT"
  kubectl_cmd wait --for=condition=Established crd/kustomizations.kustomize.toolkit.fluxcd.io --timeout="$WAIT_TIMEOUT"
  kubectl_cmd -n flux-system rollout status deployment/source-controller --timeout="$WAIT_TIMEOUT"
  kubectl_cmd -n flux-system rollout status deployment/kustomize-controller --timeout="$WAIT_TIMEOUT"
}

git_daemon_pod() {
  kubectl_cmd -n git-system get pods \
    -l app.kubernetes.io/name=git-daemon \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}'
}

wait_for_git_daemon() {
  local attempt
  local pod

  log "Waiting for git-daemon"
  kubectl_cmd -n git-system rollout status deployment/git-daemon --timeout="$WAIT_TIMEOUT"
  kubectl_cmd -n git-system wait deployment/git-daemon \
    --for=condition=Available \
    --timeout="$WAIT_TIMEOUT"

  for attempt in $(seq 1 60); do
    pod="$(git_daemon_pod 2>/dev/null || true)"
    if [[ -n "$pod" ]] && kubectl_cmd -n git-system exec "$pod" -c git-daemon -- git --version >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  die "git-daemon container did not become exec-ready"
}

seed_git_daemon() {
  local pod
  local repo_name="humility-${CHANNEL_ID}.git"
  local repo_path="/srv/git/${repo_name}"
  local seed_path="/tmp/humility-gitops-seed"

  pod="$(git_daemon_pod)"
  [[ -n "$pod" ]] || die "git-daemon pod not found"

  log "Seeding ${repo_path} from ${SNAPSHOT_DIR}"
  kubectl_cmd -n git-system exec "$pod" -c git-daemon -- sh -c "
    set -e
    rm -rf '${seed_path}'
    mkdir -p '${seed_path}' /srv/git
    if [ ! -d '${repo_path}' ]; then
      git init --bare '${repo_path}' >/dev/null
    fi
  "

  tar -C "$SNAPSHOT_DIR" -cf - . \
    | kubectl_cmd -n git-system exec -i "$pod" -c git-daemon -- tar -C "$seed_path" -xf -

  kubectl_cmd -n git-system exec "$pod" -c git-daemon -- sh -c "
    set -e
    cd '${seed_path}'
    git config --global --add safe.directory '${seed_path}'
    git init --initial-branch=main >/dev/null
    git config user.email 'gitops-seed@humility.local'
    git config user.name 'Humility GitOps Seed'
    git add -A
    git commit -m 'seed local gitops snapshot' >/dev/null
    git remote remove origin >/dev/null 2>&1 || true
    git remote add origin '${repo_path}'
    git push --force origin main >/dev/null
    git --git-dir='${repo_path}' symbolic-ref HEAD refs/heads/main
    git --git-dir='${repo_path}' update-server-info
  "
}

ensure_age_secret() {
  if kubectl_cmd -n "$DECRYPTION_SECRET_NAMESPACE" get secret "$SOPS_AGE_SECRET_NAME" >/dev/null 2>&1; then
    log "Secret/${SOPS_AGE_SECRET_NAME} already exists in ${DECRYPTION_SECRET_NAMESPACE}"
    return 0
  fi

  log "Creating Secret/${SOPS_AGE_SECRET_NAME} in ${DECRYPTION_SECRET_NAMESPACE}"
  bash "$AGE_BOOTSTRAP" \
    --channel "$CHANNEL_ID" \
    --kubeconfig "$KUBECONFIG_PATH" \
    --namespace "$DECRYPTION_SECRET_NAMESPACE" \
    --secret-name "$SOPS_AGE_SECRET_NAME" >/dev/null
}

apply_source_crs() {
  log "Applying Flux source CRs"
  kubectl_cmd apply -f "${SNAPSHOT_DIR}/gitops/sources/${CHANNEL_ID}/gitrepository.yaml"
  kubectl_cmd apply -f "${SNAPSHOT_DIR}/gitops/sources/${CHANNEL_ID}/kustomization.yaml"
}

request_kustomization_reconciliation() {
  local requested_at
  requested_at="$(date +%s)"

  log "Requesting Kustomization/${SOURCE_NAME} reconciliation"
  kubectl_cmd -n "$SOURCE_NAMESPACE" annotate "kustomization/${SOURCE_NAME}" \
    "reconcile.fluxcd.io/requestedAt=${requested_at}" \
    --overwrite >/dev/null 2>&1 || true

  if command -v flux >/dev/null 2>&1; then
    flux_cmd reconcile kustomization "$SOURCE_NAME" --namespace "$SOURCE_NAMESPACE" --with-source --timeout=30s >/dev/null 2>&1 || true
  fi
}

wait_for_source_reconciliation() {
  log "Waiting for GitRepository/${SOURCE_NAME}"
  if command -v flux >/dev/null 2>&1; then
    flux_cmd reconcile source git "$SOURCE_NAME" --namespace "$SOURCE_NAMESPACE" --timeout="$WAIT_TIMEOUT" || true
  fi
  kubectl_cmd -n "$SOURCE_NAMESPACE" wait "gitrepository/${SOURCE_NAME}" \
    --for=condition=Ready \
    --timeout="$WAIT_TIMEOUT"
}

wait_for_reconciliation() {
  log "Waiting for Kustomization/${SOURCE_NAME}"
  if command -v flux >/dev/null 2>&1; then
    flux_cmd reconcile kustomization "$SOURCE_NAME" --namespace "$SOURCE_NAMESPACE" --with-source --timeout="$WAIT_TIMEOUT" || true
  fi
  kubectl_cmd -n "$SOURCE_NAMESPACE" wait "kustomization/${SOURCE_NAME}" \
    --for=condition=Ready \
    --timeout="$WAIT_TIMEOUT"
}

wait_for_rollout() {
  local namespace="$1"
  local resource="$2"
  local description="$3"
  local attempt

  log "Waiting for ${description}"
  for attempt in $(seq 1 120); do
    if kubectl_cmd -n "$namespace" get "$resource" >/dev/null 2>&1 \
      && kubectl_cmd -n "$namespace" rollout status "$resource" --timeout=10s >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done

  kubectl_cmd -n "$namespace" get "$resource" -o wide || true
  die "${description} did not roll out"
}

wait_for_secret_key() {
  local namespace="$1"
  local secret="$2"
  local key="$3"
  local description="$4"
  local attempt
  local value

  log "Waiting for ${description}"
  for attempt in $(seq 1 120); do
    value="$(kubectl_cmd -n "$namespace" get secret "$secret" -o "jsonpath={.data.${key}}" 2>/dev/null || true)"
    if [[ -n "$value" ]]; then
      return 0
    fi
    sleep 3
  done

  die "${description} did not appear"
}

sample_infisical_secret_ready() {
  kubectl_cmd -n "$INFISICAL_SAMPLE_NAMESPACE" get infisicalsecret "$INFISICAL_SAMPLE_NAME" -o json 2>/dev/null \
    | "$PYTHON_BIN" -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") not in {"secrets.infisical.com/ReadyToSyncSecrets", "Ready"}:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)

raise SystemExit(1)
'
}

wait_for_sample_infisical_secret() {
  local attempt

  log "Waiting for InfisicalSecret/${INFISICAL_SAMPLE_NAME} ReadyToSyncSecrets=True"
  for attempt in $(seq 1 60); do
    if sample_infisical_secret_ready; then
      return 0
    fi
    sleep 3
  done

  kubectl_cmd -n "$INFISICAL_SAMPLE_NAMESPACE" get infisicalsecret "$INFISICAL_SAMPLE_NAME" -o yaml || true
  die "InfisicalSecret/${INFISICAL_SAMPLE_NAME} did not report ReadyToSyncSecrets=True"
}

wait_for_target_secret() {
  local encoded
  local decoded
  local attempt

  log "Waiting for Secret/${INFISICAL_SAMPLE_NAME} sample key"
  for attempt in $(seq 1 60); do
    encoded="$(kubectl_cmd -n "$INFISICAL_SAMPLE_NAMESPACE" get secret "$INFISICAL_SAMPLE_NAME" -o "jsonpath={.data.${INFISICAL_SAMPLE_KEY}}" 2>/dev/null || true)"
    if [[ -n "$encoded" ]]; then
      decoded="$(printf '%s' "$encoded" | base64 --decode 2>/dev/null || true)"
      if [[ "$decoded" == "$INFISICAL_SAMPLE_VALUE" ]]; then
        return 0
      fi
    fi
    sleep 3
  done

  die "Secret/${INFISICAL_SAMPLE_NAME} did not contain expected ${INFISICAL_SAMPLE_KEY}"
}

bootstrap_infisical_identity() {
  log "Bootstrapping Infisical Operator Universal Auth identity"
  bash "$INFISICAL_BOOTSTRAP" --channel "$CHANNEL_ID" --kubeconfig "$KUBECONFIG_PATH"
}

wait_for_infisical_server() {
  wait_for_rollout "$INFISICAL_NAMESPACE" "statefulset/${INFISICAL_POSTGRES_STATEFULSET}" "Infisical Postgres StatefulSet"
  wait_for_rollout "$INFISICAL_NAMESPACE" "statefulset/${INFISICAL_REDIS_STATEFULSET}" "Infisical Redis StatefulSet"
  wait_for_rollout "$INFISICAL_NAMESPACE" "deployment/${INFISICAL_SERVER_DEPLOYMENT}" "Infisical server Deployment"
  kubectl_cmd -n "$INFISICAL_NAMESPACE" wait "deployment/${INFISICAL_SERVER_DEPLOYMENT}" \
    --for=condition=Available \
    --timeout="$INFISICAL_WAIT_TIMEOUT"
}

wait_for_infisical_runtime() {
  wait_for_rollout "$INFISICAL_NAMESPACE" "deployment/${INFISICAL_OPERATOR_DEPLOYMENT}" "Infisical Operator Deployment"
  wait_for_secret_key "$INFISICAL_UA_SECRET_NAMESPACE" "$INFISICAL_UA_SECRET_NAME" "clientId" "Operator UA Secret clientId"
  wait_for_secret_key "$INFISICAL_UA_SECRET_NAMESPACE" "$INFISICAL_UA_SECRET_NAME" "clientSecret" "Operator UA Secret clientSecret"
  wait_for_sample_infisical_secret
  wait_for_target_secret
}

main() {
  parse_args "$@"

  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
  command -v tar >/dev/null 2>&1 || die "tar is required"
  command -v base64 >/dev/null 2>&1 || die "base64 is required"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"

  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_ID")"
  target="$(json_field target)"
  [[ "$target" == "k3d-local" ]] || die "channel '${CHANNEL_ID}' target is '${target}', expected k3d-local"

  KUBECONFIG_PATH="$(json_field kubeconfig_path)"
  KUBECONFIG_PATH="${KUBECONFIG_PATH/#\~/$HOME}"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  SOURCE_NAME="$(json_field source_name)"
  SOURCE_NAMESPACE="$(json_field source_namespace)"
  SOPS_AGE_SECRET_NAME="$(json_field sops_age_secret_name)"
  DECRYPTION_SECRET_NAMESPACE="$(json_field decryption_secret_namespace)"
  INFISICAL_NAMESPACE="$(json_field infisical_operator_namespace)"
  INFISICAL_UA_SECRET_NAME="$(json_field infisical_universal_auth_secret_name)"
  INFISICAL_UA_SECRET_NAMESPACE="$(json_field infisical_universal_auth_secret_namespace)"
  [[ "$DECRYPTION_SECRET_NAMESPACE" == "$SOURCE_NAMESPACE" ]] || die "Flux SOPS secret namespace must match Kustomization namespace"

  SNAPSHOT_DIR="${REPO_ROOT}/.tmp/gitops-source/${CHANNEL_ID}"
  "$PYTHON_BIN" "$RENDERER" --channel "$CHANNEL_ID" --out "$SNAPSHOT_DIR"

  log "Applying Flux controllers"
  kubectl_cmd apply -f "${REPO_ROOT}/gitops/flux/gotk-components.yaml"
  wait_for_flux_controllers

  log "Applying in-cluster Git daemon"
  kubectl_cmd apply -f "${REPO_ROOT}/gitops/sources/local/git-daemon.yaml"
  wait_for_git_daemon
  seed_git_daemon

  ensure_age_secret
  apply_source_crs
  wait_for_source_reconciliation
  request_kustomization_reconciliation
  wait_for_infisical_server
  bootstrap_infisical_identity
  wait_for_infisical_runtime
  wait_for_reconciliation

  log "Flux post-install complete for channel '${CHANNEL_ID}'"
}

main "$@"
