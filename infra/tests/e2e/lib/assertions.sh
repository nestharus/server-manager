#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi

E2E_ARTIFACT_DIR="${E2E_ARTIFACT_DIR:-${REPO_ROOT}/.tmp/init-119-e2e}"
E2E_DIAGNOSTICS_DIR="${E2E_DIAGNOSTICS_DIR:-${REPO_ROOT}/.tmp/init-119-bringup-diagnostics}"
KUBECONFIG_PATH="${KUBECONFIG_PATH:-${HOME}/.kube/humility-local.yaml}"

E2E_FLOW_ID=""
E2E_FLOW_NAME=""
E2E_PASS_COUNT=0
E2E_SKIP_COUNT=0
E2E_EVIDENCE=()

e2e_init() {
  E2E_FLOW_ID="$1"
  E2E_FLOW_NAME="$2"
  mkdir -p "${E2E_ARTIFACT_DIR}/logs/${E2E_FLOW_ID}" "$E2E_DIAGNOSTICS_DIR"
  echo "FLOW: ${E2E_FLOW_ID} ${E2E_FLOW_NAME}"
}

e2e_log_path() {
  local name="$1"
  printf '%s/logs/%s/%s.log' "$E2E_ARTIFACT_DIR" "$E2E_FLOW_ID" "$name"
}

e2e_pass() {
  echo "PASS: $1"
  E2E_PASS_COUNT=$((E2E_PASS_COUNT + 1))
  E2E_EVIDENCE+=("$1")
}

e2e_note() {
  echo "NOTE: $1"
  E2E_EVIDENCE+=("$1")
}

e2e_skip_flow() {
  local reason="$1"
  echo "SKIP: ${reason}"
  echo "E2E_STATUS: SKIP"
  echo "E2E_REASON: ${reason}"
  exit 0
}

e2e_fail() {
  local reason="$1"
  echo "FAIL: ${reason}" >&2
  echo "E2E_STATUS: FAIL"
  echo "E2E_REASON: ${reason}"
  exit 1
}

e2e_finish() {
  echo "E2E_STATUS: PASS"
  echo "E2E_PASS_COUNT: ${E2E_PASS_COUNT}"
  if [[ "${#E2E_EVIDENCE[@]}" -gt 0 ]]; then
    printf 'E2E_EVIDENCE: %s\n' "${E2E_EVIDENCE[0]}"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || e2e_fail "missing required command: $1"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

run_logged() {
  local name="$1"
  shift
  local log_file
  log_file="$(e2e_log_path "$name")"
  echo "RUN: $*" | tee "$log_file"
  if "$@" >>"$log_file" 2>&1; then
    e2e_pass "$name completed"
    return 0
  fi
  tail -n 80 "$log_file" >&2 || true
  e2e_fail "$name failed; see ${log_file}"
}

run_validator() {
  local name="$1"
  shift
  local script="$1"
  shift
  run_logged "$name" "${REPO_ROOT}/${script}" "$@"
}

wait_condition() {
  local description="$1"
  local namespace="$2"
  local resource="$3"
  local condition="$4"
  local timeout="${5:-300s}"

  kubectl_cmd -n "$namespace" wait "$resource" --for="$condition" --timeout="$timeout" >/dev/null \
    || e2e_fail "timed out waiting for ${description}"
  e2e_pass "${description}"
}

json_condition_true() {
  local namespace="$1"
  local resource="$2"
  local condition_type="$3"
  local payload

  payload="$(kubectl_cmd -n "$namespace" get "$resource" -o json)"
  python3 -c '
import json
import sys

condition_type = sys.argv[1]
payload = json.load(sys.stdin)
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
}

capture_k8s_diagnostics() {
  local component="$1"
  local out_dir="${E2E_DIAGNOSTICS_DIR}/${component}"
  mkdir -p "$out_dir"
  if [[ ! -f "$KUBECONFIG_PATH" ]] || ! command -v kubectl >/dev/null 2>&1; then
    return 0
  fi
  kubectl_cmd get nodes -o wide >"${out_dir}/nodes.txt" 2>&1 || true
  kubectl_cmd get pods -A -o wide >"${out_dir}/pods.txt" 2>&1 || true
  kubectl_cmd get events -A --sort-by=.lastTimestamp >"${out_dir}/events.txt" 2>&1 || true
  kubectl_cmd get kustomizations.kustomize.toolkit.fluxcd.io -A -o yaml >"${out_dir}/flux-kustomizations.yaml" 2>&1 || true
  kubectl_cmd get gitrepositories.source.toolkit.fluxcd.io -A -o yaml >"${out_dir}/flux-sources.yaml" 2>&1 || true
  kubectl_cmd get infisicalsecrets.secrets.infisical.com -A -o yaml >"${out_dir}/infisicalsecrets.yaml" 2>&1 || true
  kubectl_cmd describe pods -A >"${out_dir}/pod-descriptions.txt" 2>&1 || true
}

require_cluster() {
  require_command kubectl
  [[ -f "$KUBECONFIG_PATH" ]] || e2e_fail "kubeconfig not found: ${KUBECONFIG_PATH}"
  kubectl_cmd get namespace kube-system >/dev/null 2>&1 || e2e_fail "cluster API is not reachable"
}
