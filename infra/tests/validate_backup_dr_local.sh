#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
RESTORE_DRILL="${REPO_ROOT}/infra/scripts/run-cnpg-restore-drill.sh"
SNAPSHOT_SCRIPT="${REPO_ROOT}/infra/scripts/snapshot-k3d-volumes.sh"

CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESOLVED_JSON=""
KUSTOMIZE_CMD=()
TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: validate_backup_dr_local.sh [--channel local] [--kubeconfig PATH] [--static-only]

Validates INIT-112 Backup / DR:
  - top-level channel backup contract
  - local backup bucket and CNPG ScheduledBackup manifests
  - restore drill and k3d volume snapshot scripts
  - optional runtime proof through a manual backup and restore cluster
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

cleanup() {
  if [[ ${#TEMP_FILES[@]} -gt 0 ]]; then
    rm -f "${TEMP_FILES[@]+"${TEMP_FILES[@]}"}"
  fi
}

die() {
  fail "$*"
  finish
  exit 1
}

trap cleanup EXIT

parse_args() {
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
      --static-only)
        STATIC_ONLY=1
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
  jq -er "$1" <<<"$RESOLVED_JSON"
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

assert_executable() {
  local path="$1"
  [[ -x "${REPO_ROOT}/${path}" ]] && pass "executable: ${path}" || die "not executable: ${path}"
}

assert_channel_contract() {
  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  assert_json_equals '.backup.provider' 'minio' 'backup provider'
  assert_json_equals '.backup.bucket' 'humility-local-backups' 'backup bucket'
  assert_json_equals '.backup.destination_path' 's3://humility-local-backups/cnpg/local/sample-app-postgres' 'backup destination path'
  assert_json_equals '.backup.retention_policy' '7d' 'backup retention policy'
  assert_json_equals '.backup.credentials_secret_name' 'backup-object-storage' 'backup credentials Secret'
  assert_json_equals '.backup.infisical_project' 'platform-storage' 'backup Infisical project'
  assert_json_equals '.backup.infisical_path' '/object-storage/local/' 'backup Infisical path'
  pass "resolved channel backup contract"
}

assert_static_manifests() {
  local object_storage_render
  local data_plane_render
  local local_render

  assert_file "gitops/channels/local/object-storage/buckets/backup-job.yaml"
  assert_file "gitops/channels/local/data-plane/sample-app/scheduled-backup.yaml"
  assert_file "gitops/channels/local/data-plane/sample-app/backup-credentials-infisicalsecret.yaml"
  assert_file "infra/scripts/run-cnpg-restore-drill.sh"
  assert_file "infra/scripts/snapshot-k3d-volumes.sh"
  assert_executable "infra/scripts/run-cnpg-restore-drill.sh"
  assert_executable "infra/scripts/snapshot-k3d-volumes.sh"

  object_storage_render="$(mktemp)"
  data_plane_render="$(mktemp)"
  local_render="$(mktemp)"
  TEMP_FILES+=("$object_storage_render" "$data_plane_render" "$local_render")

  "${KUSTOMIZE_CMD[@]}" "${REPO_ROOT}/gitops/channels/local/object-storage" >"$object_storage_render"
  pass "object-storage raw manifests kustomize"
  "${KUSTOMIZE_CMD[@]}" "${REPO_ROOT}/gitops/channels/local/data-plane" >"$data_plane_render"
  pass "data-plane raw manifests kustomize"
  "${KUSTOMIZE_CMD[@]}" --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$local_render"
  pass "local root kustomization includes backup/DR resources"

  grep -q 'name: create-backup-bucket' "$object_storage_render" || die "missing create-backup-bucket Job"
  grep -q 'local/humility-local-backups' "$object_storage_render" || die "backup bucket Job does not create humility-local-backups"
  pass "backup bucket Job rendered"

  grep -q '^kind: ScheduledBackup$' "$data_plane_render" || die "missing ScheduledBackup kind"
  grep -q 'name: sample-app-postgres-daily' "$data_plane_render" || die "missing sample-app-postgres-daily ScheduledBackup"
  grep -Eq 'retentionPolicy:[[:space:]]+"?7d"?' "$data_plane_render" || die "missing local 7d retention policy"
  grep -q 's3://humility-local-backups/cnpg/local/sample-app-postgres' "$data_plane_render" || die "missing backup destination path"
  pass "CNPG backup schedule and retention rendered"

  if rg -n 'helm-controller|kind: HelmRelease' "$object_storage_render" "$data_plane_render" "$local_render" >/tmp/init112-helm-controller.txt; then
    cat /tmp/init112-helm-controller.txt >&2
    die "no helm-controller or HelmRelease resources"
  fi
  pass "no helm-controller or HelmRelease resources"
}

assert_runtime() {
  local drill_log

  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime restore drill skipped by --static-only"
    return
  fi

  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  command -v mc >/dev/null 2>&1 || die "mc is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  drill_log="$(mktemp)"
  TEMP_FILES+=("$drill_log")
  "$RESTORE_DRILL" --channel "$CHANNEL_REQUEST" --kubeconfig "$KUBECONFIG_PATH" | tee "$drill_log"
  grep -q '^PROOF: backup=' "$drill_log" || die "restore drill did not emit proof"
  pass "restore drill created backup in MinIO and verified restore"
}

main() {
  parse_args "$@"
  command -v jq >/dev/null 2>&1 || die "jq is required"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  configure_kustomize_cmd

  assert_channel_contract
  assert_static_manifests
  assert_runtime
  finish
}

main "$@"
