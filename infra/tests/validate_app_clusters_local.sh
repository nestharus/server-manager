#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
CLUSTER_MODE=0
STATIC_ONLY=0
CLAIM_NAMESPACE="platform-app-clusters"
CLAIM_NAME="local-sample"
APP_CLUSTER_NAME="humility-local-app"
FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fixtures/app-clusters"

usage() {
  cat <<'EOF'
Usage: validate_app_clusters_local.sh [--static-only] [--cluster] [--kubeconfig PATH]

Validates the INIT-106 local Crossplane app-cluster proof against an existing
local channel: Crossplane controllers available, provider packages healthy,
AppCluster/local-sample Ready=True, and nested k3d app cluster running.

Options:
  --static-only     Validate the contract fixtures without requiring a cluster
  --cluster          Run explicit cluster runtime validation
  --kubeconfig PATH  Kubeconfig for the local k3d channel
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

validate_static_fixtures() {
  local claim_fixture="${FIXTURE_DIR}/local-sample-appcluster.json"
  local secret_fixture="${FIXTURE_DIR}/local-sample-connection-secret.json"

  python3 - "$claim_fixture" "$secret_fixture" <<'PY'
import json
import sys

claim_path, secret_path = sys.argv[1:]

with open(claim_path, encoding="utf-8") as handle:
    claim = json.load(handle)
with open(secret_path, encoding="utf-8") as handle:
    secret = json.load(handle)


def fail(message):
    raise SystemExit(f"ERROR: {message}")


metadata = claim.get("metadata", {})
spec = claim.get("spec", {})
status = claim.get("status", {})

if claim.get("apiVersion") != "platform.humility.gg/v1alpha1":
    fail("AppCluster fixture apiVersion must be platform.humility.gg/v1alpha1")
if claim.get("kind") != "AppCluster":
    fail("claim fixture must be kind AppCluster")
if metadata.get("namespace") != "platform-app-clusters":
    fail("AppCluster fixture must live in platform-app-clusters")
if metadata.get("name") != "local-sample":
    fail("AppCluster fixture must be local-sample")

required_spec = {
    "environmentName": "local",
    "clusterClass": "dev",
    "kubernetesChannel": "stable",
    "deletionPolicy": "Orphan",
}
for key, expected in required_spec.items():
    if spec.get(key) != expected:
        fail(f"AppCluster spec.{key} must be {expected!r}")

provider_ref = spec.get("providerRef", {})
if provider_ref.get("name") != "local-k3d":
    fail("AppCluster spec.providerRef.name must be local-k3d")

node_pools = spec.get("nodePools")
if not isinstance(node_pools, list) or not node_pools:
    fail("AppCluster spec.nodePools must define at least one supported pool")
for pool in node_pools:
    if not pool.get("name") or int(pool.get("replicas", 0)) < 1:
        fail("each AppCluster node pool needs a name and at least one replica")

write_ref = spec.get("writeConnectionSecretToRef", {})
status_ref = status.get("connectionSecretRef", {})
if not write_ref:
    fail("AppCluster spec.writeConnectionSecretToRef is required")
if status_ref != write_ref:
    fail("status.connectionSecretRef must match spec.writeConnectionSecretToRef")

generation = metadata.get("generation")
ready = None
for condition in status.get("conditions", []):
    if condition.get("type") == "Ready":
        ready = condition
        break
if ready is None:
    fail("AppCluster status.conditions must include Ready")
if str(ready.get("status")) != "True":
    fail("AppCluster Ready condition must be True")
if ready.get("observedGeneration") != generation:
    fail("Ready observedGeneration must match metadata.generation")

for key in ("clusterID", "externalID", "apiEndpoint"):
    if not status.get(key):
        fail(f"AppCluster status.{key} is required")

secret_metadata = secret.get("metadata", {})
if secret.get("apiVersion") != "v1" or secret.get("kind") != "Secret":
    fail("connection fixture must be a v1 Secret")
if secret_metadata.get("name") != write_ref.get("name"):
    fail("connection Secret name must match AppCluster connection reference")
if secret_metadata.get("namespace") != write_ref.get("namespace"):
    fail("connection Secret namespace must match AppCluster connection reference")

labels = secret_metadata.get("labels", {})
if labels.get("platform.humility.gg/appcluster-name") != metadata.get("name"):
    fail("connection Secret must label the source AppCluster name")
if labels.get("platform.humility.gg/appcluster-namespace") != metadata.get("namespace"):
    fail("connection Secret must label the source AppCluster namespace")

string_data = secret.get("stringData", {})
if not string_data.get("kubeconfig"):
    fail("connection Secret must publish kubeconfig material")
if string_data.get("apiEndpoint") != status.get("apiEndpoint"):
    fail("connection Secret apiEndpoint must match AppCluster status.apiEndpoint")
if string_data.get("clusterID") != status.get("clusterID"):
    fail("connection Secret clusterID must match AppCluster status.clusterID")
PY
}

assert_runtime_connection_contract() {
  local claim_json
  local secret_json
  local secret_name
  local secret_namespace

  claim_json="$(mktemp)"
  kubectl_cmd -n "${CLAIM_NAMESPACE}" get appcluster.platform.humility.gg "${CLAIM_NAME}" -o json >"${claim_json}"

  mapfile -t secret_ref < <(python3 - "$claim_json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    claim = json.load(handle)

status = claim.get("status", {})
ref = status.get("connectionSecretRef", {})
if not ref.get("name") or not ref.get("namespace"):
    raise SystemExit("missing status.connectionSecretRef.name/namespace")
for key in ("clusterID", "externalID", "apiEndpoint"):
    if not status.get(key):
        raise SystemExit(f"missing status.{key}")
print(ref["namespace"])
print(ref["name"])
PY
  )
  rm -f "${claim_json}"

  [[ "${#secret_ref[@]}" -eq 2 ]] || die "AppCluster/${CLAIM_NAME} did not publish a connection secret reference"
  secret_namespace="${secret_ref[0]}"
  secret_name="${secret_ref[1]}"

  secret_json="$(mktemp)"
  kubectl_cmd -n "${secret_namespace}" get secret "${secret_name}" -o json >"${secret_json}"
  python3 - "${secret_json}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    secret = json.load(handle)
data = secret.get("data", {})
if not data.get("kubeconfig"):
    raise SystemExit("connection Secret is missing data.kubeconfig")
PY
  rm -f "${secret_json}"
  log "PASS: AppCluster/${CLAIM_NAME} published connection Secret ${secret_namespace}/${secret_name}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --static-only)
      STATIC_ONLY=1
      ;;
    --cluster)
      CLUSTER_MODE=1
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
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

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

wait_json_condition() {
  local description="$1"
  local command_json="$2"
  local condition_type="$3"
  local attempts="${4:-160}"
  local attempt
  local payload

  for attempt in $(seq 1 "$attempts"); do
    payload="$(eval "$command_json" 2>/dev/null || true)"
    if python3 -c '
import json
import sys

condition_type = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") != condition_type:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)
raise SystemExit(1)
' "$condition_type" <<<"$payload"
    then
      return 0
    fi
    sleep 3
  done

  echo "Timed out waiting for ${description}" >&2
  return 1
}

require_command python3
if [[ "$STATIC_ONLY" -eq 1 ]]; then
  validate_static_fixtures
  log "PASS: AppCluster fixture contract is valid"
  exit 0
fi

require_command kubectl
require_command k3d
if [[ "$CLUSTER_MODE" -eq 1 ]]; then
  log "Cluster runtime mode requested"
fi
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl_cmd -n crossplane-system wait deployment/crossplane --for=condition=Available --timeout=300s >/dev/null
kubectl_cmd -n crossplane-system wait deployment/crossplane-rbac-manager --for=condition=Available --timeout=300s >/dev/null
log "PASS: Crossplane Deployments Available"

wait_json_condition \
  "Provider/provider-kubernetes Healthy" \
  "kubectl_cmd get provider.pkg.crossplane.io provider-kubernetes -o json" \
  "Healthy"
log "PASS: Provider/provider-kubernetes Healthy=True"

wait_json_condition \
  "Provider/provider-vultr Healthy" \
  "kubectl_cmd get provider.pkg.crossplane.io provider-vultr -o json" \
  "Healthy"
log "PASS: Provider/provider-vultr Healthy=True"

wait_json_condition \
  "AppCluster/${CLAIM_NAME} Ready" \
  "kubectl_cmd -n ${CLAIM_NAMESPACE} get appcluster.platform.humility.gg ${CLAIM_NAME} -o json" \
  "Ready" \
  240
log "PASS: AppCluster/${CLAIM_NAME} Ready=True"

assert_runtime_connection_contract

if k3d cluster get "$APP_CLUSTER_NAME" >/dev/null 2>&1; then
  log "PASS: nested k3d cluster ${APP_CLUSTER_NAME} exists"
else
  die "nested k3d cluster ${APP_CLUSTER_NAME} is missing"
fi

tmp_kubeconfig="$(mktemp)"
trap 'rm -f "$tmp_kubeconfig"' EXIT
k3d kubeconfig get "$APP_CLUSTER_NAME" >"$tmp_kubeconfig"
kubectl --kubeconfig "$tmp_kubeconfig" wait nodes --all --for=condition=Ready --timeout=180s >/dev/null
log "PASS: nested k3d cluster ${APP_CLUSTER_NAME} nodes Ready"
