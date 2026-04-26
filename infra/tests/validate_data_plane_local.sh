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
RESOLVED_JSON=""
KUSTOMIZE_CMD=()
TEMP_FILES=()
CNPG_NAMESPACE=""
ATLAS_NAMESPACE=""
SAMPLE_NAMESPACE=""
SAMPLE_CLUSTER=""
SAMPLE_SERVICE=""
APP_SECRET=""
URL_SECRET=""
ATLAS_MIGRATION=""
VERIFY_TABLE=""

usage() {
  cat <<'EOF'
Usage: validate_data_plane_local.sh [--channel local] [--kubeconfig PATH] [--static-only]

Validates INIT-111 data plane:
  - channel data_plane schema resolution
  - raw CNPG and Atlas manifests
  - sample PG Cluster, Infisical credential, backup target, and Atlas migration manifests
  - optional runtime proof: CNPG Cluster Ready, AtlasMigration Ready, psql connect, schema verify

Options:
  --channel <id>     Channel id to resolve (default: local)
  --kubeconfig PATH  Kubeconfig for the local k3d channel
  --static-only      Skip Kubernetes runtime proof
  -h, --help         Show this help
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

cleanup() {
  if [[ ${#TEMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]+"${TEMP_FILES[@]}"}"
  fi
}

finish() {
  echo "RESULT: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
}

die() {
  fail "$*"
  finish
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift 2
        continue
        ;;
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift 2
        continue
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

configure_kustomize_cmd() {
  if command -v kubectl >/dev/null 2>&1; then
    KUSTOMIZE_CMD=(kubectl kustomize)
  elif command -v kustomize >/dev/null 2>&1; then
    KUSTOMIZE_CMD=(kustomize build)
  else
    die "kubectl or kustomize is required for static manifest rendering"
  fi
}

json_field() {
  local expression="$1"
  jq -er "$expression" <<<"$RESOLVED_JSON"
}

assert_json_equals() {
  local expression="$1"
  local expected="$2"
  local description="$3"
  local actual

  actual="$(json_field "$expression")"
  [[ "$actual" == "$expected" ]] || die "expected ${description} to be ${expected}, got: ${actual}"
}

assert_file() {
  local path="$1"
  [[ -f "${REPO_ROOT}/${path}" ]] && pass "exists: ${path}" || die "missing: ${path}"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

wait_json_condition() {
  local description="$1"
  local namespace="$2"
  local resource="$3"
  local condition_type="$4"
  local attempts="${5:-120}"
  local attempt
  local payload

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    payload="$(kubectl_cmd -n "$namespace" get "$resource" -o json 2>/dev/null || true)"
    if "$PYTHON_BIN" -c '
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

  kubectl_cmd -n "$namespace" get "$resource" -o yaml || true
  die "${description} did not report ${condition_type}=True"
}

wait_infisicalsecret_ready() {
  local name="$1"
  wait_json_condition "InfisicalSecret/${name}" "$SAMPLE_NAMESPACE" "infisicalsecret/${name}" "secrets.infisical.com/ReadyToSyncSecrets" 120
}

secret_key() {
  local namespace="$1"
  local secret="$2"
  local key="$3"
  kubectl_cmd -n "$namespace" get secret "$secret" -o "jsonpath={.data.${key}}" | base64 -d
}

primary_pod() {
  kubectl_cmd -n "$SAMPLE_NAMESPACE" get pods \
    -l "cnpg.io/cluster=${SAMPLE_CLUSTER},role=primary" \
    -o jsonpath='{.items[0].metadata.name}'
}

assert_channel_contract() {
  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  assert_json_equals '.id' 'local' 'channel id'
  assert_json_equals '.data_plane.provider' 'cloudnative-pg' 'data_plane provider'
  assert_json_equals '.data_plane.cnpg.operator_namespace' 'cnpg-system' 'CNPG namespace'
  assert_json_equals '.data_plane.cnpg.operator_version' '1.29.0' 'CNPG version'
  assert_json_equals '.data_plane.atlas.chart_version' '0.7.28' 'Atlas chart version'
  assert_json_equals '.data_plane.credentials.infisical_project' 'platform-databases' 'database Infisical project'
  assert_json_equals '.data_plane.credentials.infisical_path' '/postgres/local/sample-app' 'database Infisical path'
  assert_json_equals '.data_plane.backup.bucket' 'humility-local-sample' 'backup bucket'
  assert_json_equals '.data_plane.backup.endpoint' 'http://minio.minio-system.svc.cluster.local:9000' 'backup endpoint'
  pass "resolved channel data_plane contract"

  CNPG_NAMESPACE="$(json_field '.data_plane.cnpg.operator_namespace')"
  ATLAS_NAMESPACE="$(json_field '.data_plane.atlas.operator_namespace')"
  SAMPLE_NAMESPACE="$(json_field '.data_plane.sample.namespace')"
  SAMPLE_CLUSTER="$(json_field '.data_plane.sample.cluster_name')"
  SAMPLE_SERVICE="$(json_field '.data_plane.sample.service_name')"
  APP_SECRET="$(json_field '.data_plane.credentials.app_secret_name')"
  URL_SECRET="$(json_field '.data_plane.credentials.url_secret_name')"
  ATLAS_MIGRATION="$(json_field '.data_plane.migrations.atlas_migration_name')"
  VERIFY_TABLE="$(json_field '.data_plane.migrations.verify_table')"
}

assert_static_manifests() {
  local data_plane_render
  local local_render

  assert_file "gitops/channels/local/data-plane/cnpg/rendered/cnpg-1.29.0.yaml"
  assert_file "gitops/channels/local/data-plane/atlas/render-values.yaml"
  assert_file "gitops/channels/local/data-plane/atlas/rendered/atlas-operator-0.7.28.yaml"
  assert_file "gitops/channels/local/data-plane/sample-app/cluster.yaml"
  assert_file "gitops/channels/local/data-plane/sample-app/atlas-migration.yaml"
  assert_file "database/migrations/sample-app/20260426000100_init.sql"
  assert_file "database/migrations/sample-app/atlas.sum"

  data_plane_render="$(mktemp)"
  local_render="$(mktemp)"
  TEMP_FILES+=("$data_plane_render" "$local_render")
  "${KUSTOMIZE_CMD[@]}" "${REPO_ROOT}/gitops/channels/local/data-plane" >"$data_plane_render"
  pass "data-plane raw manifests kustomize"
  "${KUSTOMIZE_CMD[@]}" --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$local_render"
  pass "local root kustomization includes data-plane"

  grep -q '^kind: Cluster$' "$data_plane_render" || die "missing CNPG Cluster kind in rendered manifests"
  grep -q '^kind: AtlasMigration$' "$data_plane_render" || die "missing AtlasMigration kind in rendered manifests"
  grep -q 'name: sample-app-atlas-migrations' "$data_plane_render" || die "missing migration ConfigMap sample-app-atlas-migrations in rendered manifests"
  pass "sample Cluster and Atlas migration objects rendered"

  if rg -n '^kind: (Secret|Backup|ScheduledBackup)$' --glob '!**/rendered/**' "${REPO_ROOT}/gitops/channels/local/data-plane" >/tmp/init111-forbidden-kind.txt; then
    cat /tmp/init111-forbidden-kind.txt >&2
    die "no committed data-plane Secret, Backup, or ScheduledBackup resources"
  fi
  pass "no committed data-plane Secret, Backup, or ScheduledBackup resources"

  if rg -n 'postgres://sample_app:[^$({]' "${REPO_ROOT}/gitops" "${REPO_ROOT}/database" >/tmp/init111-secret-literal.txt; then
    cat /tmp/init111-secret-literal.txt >&2
    die "no committed database URL credential literals"
  fi
  pass "no committed database URL credential literals"

}

assert_runtime() {
  local url
  local pod
  local table_schema="${VERIFY_TABLE%%.*}"
  local table_name="${VERIFY_TABLE#*.}"

  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime proof skipped by --static-only"
    return
  fi
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  kubectl_cmd -n "$CNPG_NAMESPACE" rollout status deployment/cnpg-controller-manager --timeout=300s >/dev/null
  pass "CNPG controller Deployment Available"
  kubectl_cmd -n "$ATLAS_NAMESPACE" rollout status deployment/atlas-operator --timeout=300s >/dev/null
  pass "Atlas Operator Deployment Available"

  wait_infisicalsecret_ready "$APP_SECRET"
  pass "InfisicalSecret/${APP_SECRET} ReadyToSyncSecrets=True"
  wait_infisicalsecret_ready "$URL_SECRET"
  pass "InfisicalSecret/${URL_SECRET} ReadyToSyncSecrets=True"
  wait_infisicalsecret_ready "minio-root"
  pass "InfisicalSecret/minio-root ReadyToSyncSecrets=True"

  [[ -n "$(secret_key "$SAMPLE_NAMESPACE" "$APP_SECRET" username)" ]] || die "app username Secret key is empty"
  [[ -n "$(secret_key "$SAMPLE_NAMESPACE" "$APP_SECRET" password)" ]] || die "app password Secret key is empty"
  url="$(secret_key "$SAMPLE_NAMESPACE" "$URL_SECRET" url)"
  [[ -n "$url" ]] || die "database URL Secret key is empty"
  pass "database credentials synced with non-empty keys"

  wait_json_condition "Cluster/${SAMPLE_CLUSTER}" "$SAMPLE_NAMESPACE" "cluster/${SAMPLE_CLUSTER}" "Ready" 180
  pass "PG Cluster/${SAMPLE_CLUSTER} Ready=True"

  wait_json_condition "AtlasMigration/${ATLAS_MIGRATION}" "$SAMPLE_NAMESPACE" "atlasmigration/${ATLAS_MIGRATION}" "Ready" 180
  pass "AtlasMigration/${ATLAS_MIGRATION} Ready=True"

  pod="$(primary_pod)"
  [[ -n "$pod" ]] || die "primary Pod for ${SAMPLE_CLUSTER} not found"
  kubectl_cmd -n "$SAMPLE_NAMESPACE" exec "$pod" -c postgres -- psql "$url" -v ON_ERROR_STOP=1 -c "select 1;" >/dev/null
  pass "psql connect succeeded through ${SAMPLE_SERVICE}"

  kubectl_cmd -n "$SAMPLE_NAMESPACE" exec -i "$pod" -c postgres -- psql "$url" -v ON_ERROR_STOP=1 \
    -v "tbl_schema=${table_schema}" -v "tbl_name=${table_name}" -At \
    <<'SQL' | grep -qx 't' || die "schema table ${VERIFY_TABLE} missing"
select exists (
  select 1
  from information_schema.tables
  where table_schema = :'tbl_schema'
    and table_name = :'tbl_name'
);
SQL
  pass "schema verify found ${VERIFY_TABLE}"
}

main() {
  trap cleanup EXIT
  parse_args "$@"
  command -v jq >/dev/null 2>&1 || die "jq is required"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  command -v base64 >/dev/null 2>&1 || die "base64 is required"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  configure_kustomize_cmd

  assert_channel_contract
  assert_static_manifests
  assert_runtime
  finish
}

main "$@"
