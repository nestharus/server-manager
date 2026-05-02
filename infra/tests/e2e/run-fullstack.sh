#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
export REPO_ROOT
export E2E_ARTIFACT_DIR="${E2E_ARTIFACT_DIR:-${REPO_ROOT}/.tmp/init-119-e2e}"
export E2E_DIAGNOSTICS_DIR="${E2E_DIAGNOSTICS_DIR:-${REPO_ROOT}/.tmp/init-119-bringup-diagnostics}"
export KUBECONFIG_PATH="${KUBECONFIG_PATH:-${HOME}/.kube/humility-local.yaml}"

source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
source "${REPO_ROOT}/infra/tests/e2e/lib/bringup.sh"
source "${REPO_ROOT}/infra/tests/e2e/lib/teardown.sh"

KEEP_CLUSTER=0
SKIP_BRINGUP=0
SUMMARY_TSV="${E2E_ARTIFACT_DIR}/summary.tsv"
DOC_PATH="${REPO_ROOT}/infra/tests/e2e/status.md"

usage() {
  cat <<'EOF'
Usage: infra/tests/e2e/run-fullstack.sh [--skip-bringup] [--keep-cluster]

Runs the full INIT-119 local infra E2E suite. By default the harness deletes
the local cluster and Docker registry/cache volumes on exit, whether tests pass
or fail.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-bringup)
      SKIP_BRINGUP=1
      ;;
    --keep-cluster)
      KEEP_CLUSTER=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cleanup() {
  if [[ "$KEEP_CLUSTER" -eq 0 ]]; then
    e2e_teardown_local
  else
    echo "TEARDOWN: skipped by --keep-cluster"
  fi
}
trap cleanup EXIT

write_status_doc() {
  local generated_at
  generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    echo "# INIT-119 Infra E2E Status"
    echo
    echo "Generated: ${generated_at}"
    echo
    if [[ -f "${E2E_ARTIFACT_DIR}/bringup-seconds.txt" ]]; then
      echo "Bring-up seconds: $(cat "${E2E_ARTIFACT_DIR}/bringup-seconds.txt")"
    else
      echo "Bring-up seconds: NOT RECORDED"
    fi
    echo
    echo "| Flow | Status | Evidence |"
    echo "|---|---:|---|"
    if [[ -f "$SUMMARY_TSV" ]]; then
      while IFS=$'\t' read -r flow status evidence log_file; do
        [[ -n "$flow" ]] || continue
        evidence="${evidence//|/\\|}"
        echo "| ${flow} | ${status} | ${evidence} (log: ${log_file}) |"
      done <"$SUMMARY_TSV"
    fi
  } >"$DOC_PATH"
}

record_result() {
  local flow="$1"
  local status="$2"
  local evidence="$3"
  local log_file="$4"
  printf '%s\t%s\t%s\t%s\n' "$flow" "$status" "$evidence" "$log_file" >>"$SUMMARY_TSV"
}

run_one_test() {
  local test_file="$1"
  local flow
  local log_file
  local rc
  local status
  local evidence

  flow="$(basename "$test_file" .sh)"
  log_file="${E2E_ARTIFACT_DIR}/logs/${flow}.log"
  mkdir -p "$(dirname "$log_file")"

  echo "TEST: ${flow}"
  set +e
  "$test_file" >"$log_file" 2>&1
  rc=$?
  set -e

  status="$(awk -F': ' '/^E2E_STATUS: / { value=$2 } END { print value }' "$log_file")"
  evidence="$(awk -F': ' '/^(E2E_EVIDENCE|E2E_REASON): / { value=$2 } END { print value }' "$log_file")"
  [[ -n "$evidence" ]] || evidence="$(grep -E '^(PASS|SKIP|FAIL): ' "$log_file" | tail -n 1 | sed 's/^[A-Z]*: //' || true)"

  if [[ "$rc" -ne 0 ]]; then
    status="FAIL"
    [[ -n "$evidence" ]] || evidence="test exited ${rc}"
    capture_k8s_diagnostics "$flow"
  elif [[ -z "$status" ]]; then
    status="PASS"
  fi

  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
    *) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
  esac
  record_result "$flow" "$status" "$evidence" "$log_file"
  echo "RESULT: ${flow} ${status} ${evidence}"
}

main() {
  rm -rf "$E2E_ARTIFACT_DIR" "$E2E_DIAGNOSTICS_DIR"
  mkdir -p "${E2E_ARTIFACT_DIR}/logs" "$E2E_DIAGNOSTICS_DIR"
  : >"$SUMMARY_TSV"

  local suite_started_at
  suite_started_at="$(date +%s)"

  if [[ "$SKIP_BRINGUP" -eq 0 ]]; then
    if ! e2e_bringup_fullstack 2>&1 | tee "${E2E_ARTIFACT_DIR}/bringup.log"; then
      record_result "00-bringup" "FAIL" "full-stack bring-up failed" "${E2E_ARTIFACT_DIR}/bringup.log"
      write_status_doc
      return 1
    fi
  else
    echo "BRINGUP: skipped by --skip-bringup"
  fi

  PASS_COUNT=0
  FAIL_COUNT=0
  SKIP_COUNT=0
  local test_file
  for test_file in "${REPO_ROOT}"/infra/tests/e2e/tests/*.sh; do
    run_one_test "$test_file"
  done

  local suite_finished_at
  suite_finished_at="$(date +%s)"
  echo "SUITE_SECONDS=$((suite_finished_at - suite_started_at))" | tee "${E2E_ARTIFACT_DIR}/suite-seconds.txt"
  echo "SUMMARY: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
  write_status_doc
  [[ "$FAIL_COUNT" -eq 0 ]]
}

main "$@"
