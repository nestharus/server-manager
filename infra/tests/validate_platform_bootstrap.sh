#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RUN_CLUSTER=0

pass() {
  echo "  PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "  SKIP: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

usage() {
  cat <<'EOF'
Usage: validate_platform_bootstrap.sh [--cluster]

Validates platform bootstrap files and local channel tooling.

Options:
  --cluster   Also create, verify, and delete the local k3d cluster when tools are present
  -h, --help  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)
      RUN_CLUSTER=1
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

assert_file_exists() {
  local file="$1"
  if [[ -f "${INFRA_DIR}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "missing: ${file}"
  fi
}

assert_dir_exists() {
  local path="$1"
  if [[ -d "${INFRA_DIR}/${path}" ]]; then
    pass "directory exists: ${path}"
  else
    fail "missing directory: ${path}"
  fi
}

assert_executable() {
  local file="$1"
  if [[ -x "${INFRA_DIR}/${file}" ]]; then
    pass "executable: ${file}"
  else
    fail "not executable: ${file}"
  fi
}

assert_path_absent() {
  local path="$1"
  if [[ ! -e "${INFRA_DIR}/${path}" ]]; then
    pass "absent: ${path}"
  else
    fail "still exists: ${path}"
  fi
}

python_bin() {
  if command -v python &>/dev/null; then
    command -v python
  elif command -v python3 &>/dev/null; then
    command -v python3
  else
    return 1
  fi
}

assert_install_cluster_tools_check() {
  local output
  local status

  set +e
  output="$(bash "${INFRA_DIR}/scripts/install-cluster-tools.sh" --check --no-color 2>&1)"
  status=$?
  set -e

  if [[ "$status" -eq 0 || "$status" -eq 1 ]]; then
    pass "install-cluster-tools --check runs (${output//$'\n'/; })"
  else
    fail "install-cluster-tools --check crashed (${output//$'\n'/; })"
  fi
}

assert_bring_up_script_help_works() {
  if bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --help >/dev/null; then
    pass "bring-up-local-channel --help"
  else
    fail "bring-up-local-channel --help"
  fi
}

assert_delete_missing_local_cluster() {
  if ! command -v k3d >/dev/null 2>&1; then
    skip "delete-local-channel idempotence check requires k3d"
    return
  fi

  if bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local >/dev/null; then
    pass "delete-local-channel missing cluster is idempotent"
  else
    fail "delete-local-channel missing cluster is idempotent"
  fi
}

assert_local_cluster_can_create() {
  local kubeconfig_path="${HOME}/.kube/humility-local.yaml"
  local node_count

  if ! command -v k3d >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: k3d"
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: docker"
    return
  fi
  if ! command -v kubectl >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: kubectl"
    return
  fi

  if ! docker info >/dev/null 2>&1; then
    skip "CLUSTER: docker daemon unavailable"
    return
  fi

  if bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local; then
    pass "local k3d cluster bring-up"
  else
    fail "local k3d cluster bring-up"
    return
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    pass "local kubeconfig exists"
  else
    fail "local kubeconfig exists"
  fi

  if node_count="$(kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null | wc -l)" && [[ "$node_count" -ge 1 ]]; then
    pass "kubectl get nodes returns ${node_count} node(s)"
  else
    fail "kubectl get nodes returns at least one node"
  fi

  if bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local; then
    pass "local k3d cluster cleanup"
  else
    fail "local k3d cluster cleanup"
  fi
}

echo "=== Slice 101.01 channel contract validation ==="

for file in \
  "schemas/platform-channel.schema.json" \
  "schemas/platform-channel-resolved.schema.json" \
  "channels/local.yaml" \
  "channels/dev.yaml" \
  "channels/fixtures/local-child.yaml" \
  "channels/fixtures/dev-child.yaml" \
  "channels/fixtures/ephemeral-disabled.yaml" \
  "channels/fixtures/missing-parent.yaml" \
  "channels/fixtures/circular-a.yaml" \
  "channels/fixtures/circular-b.yaml" \
  "scripts/resolve_platform_channel.py" \
  "scripts/validate_platform_channels.py"; do
  assert_file_exists "$file"
done

for path in \
  "environments" \
  "modules/platform-cluster/main.tf" \
  "channels/customer.yaml" \
  "channels/internal.yaml" \
  "channels/e2e.yaml"; do
  assert_path_absent "$path"
done

if PYTHON_BIN="$(python_bin)"; then
  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/validate_platform_channels.py"; then
    pass "platform channel validator"
  else
    fail "platform channel validator"
  fi

  for channel in local dev local-child; do
    if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" >/dev/null; then
      pass "resolve: ${channel}"
    else
      fail "resolve: ${channel}"
    fi
  done

  missing_parent_output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel missing-parent 2>&1 >/dev/null || true)"
  if grep -q '"code": "missing_parent"' <<<"$missing_parent_output"; then
    pass "missing-parent reports missing_parent"
  else
    fail "missing-parent reports missing_parent"
  fi

  circular_output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel circular-a 2>&1 >/dev/null || true)"
  if grep -q '"code": "circular_parent"' <<<"$circular_output"; then
    pass "circular-a reports circular_parent"
  else
    fail "circular-a reports circular_parent"
  fi
else
  fail "python interpreter available"
fi

echo ""
echo "=== Slice 101.02 local k3d cluster validation ==="

for file in \
  "modules/platform-cluster-k3d/main.tf" \
  "modules/platform-cluster-k3d/variables.tf" \
  "modules/platform-cluster-k3d/outputs.tf" \
  "modules/platform-cluster-k3d/versions.tf" \
  "scripts/install-cluster-tools.sh" \
  "scripts/bring-up-local-channel.sh" \
  "scripts/delete-local-channel.sh"; do
  assert_file_exists "$file"
done

assert_dir_exists "modules/platform-cluster-k3d"
assert_executable "scripts/install-cluster-tools.sh"
assert_executable "scripts/bring-up-local-channel.sh"
assert_executable "scripts/delete-local-channel.sh"
assert_install_cluster_tools_check
assert_bring_up_script_help_works
assert_delete_missing_local_cluster

if [[ "$RUN_CLUSTER" -eq 1 ]]; then
  assert_local_cluster_can_create
else
  skip "CLUSTER: not requested; pass --cluster to create and verify local k3d"
fi

echo ""
echo "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
