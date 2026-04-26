#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"

CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
PORT="19002"
RETAIN_RESTORE=0
PORT_FORWARD_PID=""
RESTORE_CLUSTER=""
RESTORE_CREATED=0
TEMP_FILES=()
TEMP_DIRS=()

usage() {
  cat <<'EOF'
Usage: run-cnpg-restore-drill.sh [--channel local] [--kubeconfig PATH] [--port PORT] [--retain-restore]

Creates a deterministic CNPG backup/restore drill:
  - inserts a known row into the INIT-111 sample database
  - creates a manual Backup resource
  - verifies backup objects exist in MinIO
  - restores into a fresh CNPG cluster
  - verifies restored schema and the known row

The transient restore cluster is deleted unless --retain-restore is set.
EOF
}

log() {
  printf '%s\n' "$*"
}

die() {
  log "ERROR: $*" >&2
  exit 1
}

cleanup() {
  if [[ "$RETAIN_RESTORE" -eq 0 && "$RESTORE_CREATED" -eq 1 && -n "$RESTORE_CLUSTER" ]]; then
    kubectl_cmd -n "$SAMPLE_NAMESPACE" delete cluster "$RESTORE_CLUSTER" --ignore-not-found --wait=true --timeout=300s >/dev/null 2>&1 || true
    kubectl_cmd -n "$SAMPLE_NAMESPACE" delete pvc -l "cnpg.io/cluster=${RESTORE_CLUSTER}" --ignore-not-found --wait=true --timeout=300s >/dev/null 2>&1 || true
  fi
  if [[ -n "${PORT_FORWARD_PID:-}" ]] && kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
  if [[ ${#TEMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]+"${TEMP_FILES[@]}"}"
  fi
  if [[ ${#TEMP_DIRS[@]} -gt 0 ]]; then
    rm -rf "${TEMP_DIRS[@]+"${TEMP_DIRS[@]}"}"
  fi
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || die "--channel requires a value"
      CHANNEL_REQUEST="$2"
      shift 2
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || die "--port requires a value"
      PORT="$2"
      shift 2
      ;;
    --retain-restore)
      RETAIN_RESTORE=1
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
done

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

json_field() {
  jq -er "$1" <<<"$RESOLVED_JSON"
}

secret_key() {
  local namespace="$1"
  local secret="$2"
  local key="$3"
  kubectl_cmd -n "$namespace" get secret "$secret" -o "jsonpath={.data.${key}}" | base64 -d
}

primary_pod() {
  local cluster="$1"
  kubectl_cmd -n "$SAMPLE_NAMESPACE" get pods \
    -l "cnpg.io/cluster=${cluster},role=primary" \
    -o jsonpath='{.items[0].metadata.name}'
}

wait_json_condition() {
  local description="$1"
  local namespace="$2"
  local resource="$3"
  local condition_type="$4"
  local attempts="${5:-180}"
  local payload

  for _ in $(seq 1 "$attempts"); do
    payload="$(kubectl_cmd -n "$namespace" get "$resource" -o json 2>/dev/null || true)"
    if printf '%s' "$payload" | python3 -c '
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
' "$condition_type"
    then
      return 0
    fi
    sleep 5
  done

  kubectl_cmd -n "$namespace" get "$resource" -o yaml || true
  die "${description} did not report ${condition_type}=True"
}

wait_backup_completed() {
  local backup_name="$1"
  local payload
  local phase

  for _ in $(seq 1 240); do
    payload="$(kubectl_cmd -n "$SAMPLE_NAMESPACE" get "backup/${backup_name}" -o json 2>/dev/null || true)"
    phase="$(jq -r '.status.phase // ""' <<<"$payload" 2>/dev/null || true)"
    case "${phase,,}" in
      completed|succeeded)
        return 0
        ;;
      failed|error)
        kubectl_cmd -n "$SAMPLE_NAMESPACE" get "backup/${backup_name}" -o yaml || true
        die "Backup/${backup_name} failed"
        ;;
    esac
    sleep 5
  done

  kubectl_cmd -n "$SAMPLE_NAMESPACE" get "backup/${backup_name}" -o yaml || true
  die "Backup/${backup_name} did not complete"
}

minio_ready_pod() {
  kubectl_cmd -n minio-system get pods -l app.kubernetes.io/name=minio -o json | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
for pod in payload.get("items", []):
    if pod.get("metadata", {}).get("deletionTimestamp"):
        continue
    if pod.get("status", {}).get("phase") != "Running":
        continue
    for condition in pod.get("status", {}).get("conditions", []):
        if condition.get("type") == "Ready" and str(condition.get("status")) == "True":
            print(pod.get("metadata", {}).get("name", ""))
            raise SystemExit(0)
raise SystemExit(1)
'
}

start_port_forward() {
  local log_file="${REPO_ROOT}/.tmp/init-112-minio-port-forward.log"
  local pod

  mkdir -p "${REPO_ROOT}/.tmp"
  : >"$log_file"
  pod="$(minio_ready_pod)" || die "no Ready MinIO pod available for port-forward"
  kubectl_cmd -n minio-system port-forward --address 127.0.0.1 "pod/${pod}" "${PORT}:9000" >"$log_file" 2>&1 &
  PORT_FORWARD_PID="$!"

  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${PORT}/minio/health/live" >/dev/null 2>&1; then
      return
    fi
    if ! kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
      die "kubectl port-forward exited early; see ${log_file}"
    fi
    sleep 1
  done

  die "MinIO API did not become reachable on localhost:${PORT}; see ${log_file}"
}

need_command kubectl
need_command jq
need_command python3
need_command base64
need_command curl
need_command mc

[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

RESOLVED_JSON="$(python3 "$RESOLVER" --channel "$CHANNEL_REQUEST")"
BACKUP_PROVIDER="$(json_field '.backup.provider')"
[[ "$BACKUP_PROVIDER" == "minio" ]] || die "restore drill only supports local MinIO backup provider, got ${BACKUP_PROVIDER}"

SAMPLE_NAMESPACE="$(json_field '.data_plane.sample.namespace')"
SAMPLE_CLUSTER="$(json_field '.data_plane.sample.cluster_name')"
SAMPLE_DATABASE="$(json_field '.data_plane.sample.database')"
SAMPLE_OWNER="$(json_field '.data_plane.sample.owner')"
SAMPLE_STORAGE_SIZE="$(json_field '.data_plane.sample.storage_size')"
POSTGRES_IMAGE="$(json_field '.data_plane.cnpg.postgres_image')"
VERIFY_TABLE="$(json_field '.data_plane.migrations.verify_table')"
URL_SECRET="$(json_field '.data_plane.credentials.url_secret_name')"
BACKUP_BUCKET="$(json_field '.backup.bucket')"
BACKUP_ENDPOINT="$(json_field '.backup.endpoint')"
BACKUP_DESTINATION="$(json_field '.backup.destination_path')"
BACKUP_SECRET="$(json_field '.backup.credentials_secret_name')"
SCHEDULED_BACKUP="${SAMPLE_CLUSTER}-daily"
BACKUP_PREFIX="${BACKUP_DESTINATION#s3://${BACKUP_BUCKET}/}"
STAMP="$(date -u +%Y%m%d%H%M%S)"
BACKUP_NAME="init-112-drill-${STAMP}"
RESTORE_CLUSTER="${SAMPLE_CLUSTER}-restore-${STAMP}"
ROW_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
ROW_NAME="init-112-drill-${STAMP}"

kubectl_cmd -n minio-system wait job/create-backup-bucket --for=condition=Complete --timeout=300s >/dev/null
log "PASS: Job/create-backup-bucket Complete"
kubectl_cmd -n "$SAMPLE_NAMESPACE" get scheduledbackup "$SCHEDULED_BACKUP" >/dev/null
log "PASS: ScheduledBackup/${SCHEDULED_BACKUP} exists"
wait_json_condition "Cluster/${SAMPLE_CLUSTER}" "$SAMPLE_NAMESPACE" "cluster/${SAMPLE_CLUSTER}" "Ready" 180
log "PASS: Cluster/${SAMPLE_CLUSTER} Ready=True"

SOURCE_POD="$(primary_pod "$SAMPLE_CLUSTER")"
[[ -n "$SOURCE_POD" ]] || die "primary Pod for ${SAMPLE_CLUSTER} not found"
SOURCE_URL="$(secret_key "$SAMPLE_NAMESPACE" "$URL_SECRET" url)"
[[ -n "$SOURCE_URL" ]] || die "database URL Secret key is empty"

kubectl_cmd -n "$SAMPLE_NAMESPACE" exec -i "$SOURCE_POD" -c postgres -- psql "$SOURCE_URL" -v ON_ERROR_STOP=1 \
  -v "row_id=${ROW_ID}" -v "row_name=${ROW_NAME}" <<'SQL' >/dev/null
insert into sample_app.widgets (id, name)
values (:'row_id'::uuid, :'row_name')
on conflict (id) do update set name = excluded.name;
SQL
log "PASS: inserted drill row ${ROW_ID}"

kubectl_cmd -n "$SAMPLE_NAMESPACE" apply -f - <<EOF >/dev/null
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: ${BACKUP_NAME}
  namespace: ${SAMPLE_NAMESPACE}
  labels:
    app.kubernetes.io/name: ${SAMPLE_CLUSTER}
    platform.humility.gg/init: "112"
spec:
  method: barmanObjectStore
  cluster:
    name: ${SAMPLE_CLUSTER}
EOF
wait_backup_completed "$BACKUP_NAME"
BACKUP_ID="$(kubectl_cmd -n "$SAMPLE_NAMESPACE" get "backup/${BACKUP_NAME}" -o jsonpath='{.status.backupId}' 2>/dev/null || true)"
log "PASS: Backup/${BACKUP_NAME} completed"

start_port_forward
MC_CONFIG_DIR="$(mktemp -d)"
TEMP_DIRS+=("$MC_CONFIG_DIR")
export MC_CONFIG_DIR
BACKUP_ACCESS_KEY="$(secret_key "$SAMPLE_NAMESPACE" "$BACKUP_SECRET" MINIO_ROOT_USER)"
BACKUP_SECRET_KEY="$(secret_key "$SAMPLE_NAMESPACE" "$BACKUP_SECRET" MINIO_ROOT_PASSWORD)"
mc alias set local-minio "http://127.0.0.1:${PORT}" "$BACKUP_ACCESS_KEY" "$BACKUP_SECRET_KEY" >/dev/null
mc ls "local-minio/${BACKUP_BUCKET}" >/dev/null
set +e
OBJECT_COUNT="$(mc ls --recursive "local-minio/${BACKUP_BUCKET}/${BACKUP_PREFIX}" 2>/dev/null | wc -l | tr -d ' ')"
set -e
[[ "${OBJECT_COUNT:-0}" -gt 0 ]] || die "no backup objects found under ${BACKUP_BUCKET}/${BACKUP_PREFIX}"
log "PASS: MinIO contains ${OBJECT_COUNT} backup object(s) under ${BACKUP_BUCKET}/${BACKUP_PREFIX}"

kubectl_cmd -n "$SAMPLE_NAMESPACE" apply -f - <<EOF >/dev/null
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ${RESTORE_CLUSTER}
  namespace: ${SAMPLE_NAMESPACE}
  labels:
    app.kubernetes.io/name: ${RESTORE_CLUSTER}
    platform.humility.gg/init: "112"
spec:
  instances: 1
  imageName: ${POSTGRES_IMAGE}
  bootstrap:
    recovery:
      source: ${SAMPLE_CLUSTER}
      database: ${SAMPLE_DATABASE}
      owner: ${SAMPLE_OWNER}
  externalClusters:
    - name: ${SAMPLE_CLUSTER}
      barmanObjectStore:
        destinationPath: ${BACKUP_DESTINATION}
        endpointURL: ${BACKUP_ENDPOINT}
        s3Credentials:
          accessKeyId:
            name: ${BACKUP_SECRET}
            key: MINIO_ROOT_USER
          secretAccessKey:
            name: ${BACKUP_SECRET}
            key: MINIO_ROOT_PASSWORD
        wal:
          compression: gzip
  storage:
    size: ${SAMPLE_STORAGE_SIZE}
EOF
RESTORE_CREATED=1
wait_json_condition "Cluster/${RESTORE_CLUSTER}" "$SAMPLE_NAMESPACE" "cluster/${RESTORE_CLUSTER}" "Ready" 240
log "PASS: restore Cluster/${RESTORE_CLUSTER} Ready=True"

RESTORE_POD="$(primary_pod "$RESTORE_CLUSTER")"
[[ -n "$RESTORE_POD" ]] || die "primary Pod for ${RESTORE_CLUSTER} not found"
TABLE_SCHEMA="${VERIFY_TABLE%%.*}"
TABLE_NAME="${VERIFY_TABLE#*.}"
RESTORE_RESULT="$(kubectl_cmd -n "$SAMPLE_NAMESPACE" exec -i "$RESTORE_POD" -c postgres -- psql -d "$SAMPLE_DATABASE" -v ON_ERROR_STOP=1 \
  -v "tbl_schema=${TABLE_SCHEMA}" -v "tbl_name=${TABLE_NAME}" -v "row_id=${ROW_ID}" -At <<'SQL'
select exists (
  select 1
  from information_schema.tables
  where table_schema = :'tbl_schema'
    and table_name = :'tbl_name'
);
select exists (
  select 1
  from sample_app.widgets
  where id = :'row_id'::uuid
);
SQL
)"
printf '%s\n' "$RESTORE_RESULT" | sed -n '1p' | grep -qx 't' || die "restored schema table ${VERIFY_TABLE} missing"
printf '%s\n' "$RESTORE_RESULT" | sed -n '2p' | grep -qx 't' || die "restored drill row ${ROW_ID} missing"
log "PASS: restore verified ${VERIFY_TABLE} and drill row ${ROW_ID}"

log "PROOF: backup=${BACKUP_NAME} backup_id=${BACKUP_ID:-unknown} bucket=${BACKUP_BUCKET} prefix=${BACKUP_PREFIX} restore_cluster=${RESTORE_CLUSTER} row=${ROW_ID}"
