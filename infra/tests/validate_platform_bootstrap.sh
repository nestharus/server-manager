#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RUN_CLUSTER=0
CLUSTER_EXERCISED=0

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
  --cluster   Run the full local k3d bring-up, kubectl, idempotency, and delete proof
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

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  local description="$3"

  if grep -q -- "$pattern" "${INFRA_DIR}/${file}"; then
    pass "$description"
  else
    fail "$description"
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

assert_vms_module_present() {
  for file in \
    "modules/platform-cluster-vms/main.tf" \
    "modules/platform-cluster-vms/variables.tf" \
    "modules/platform-cluster-vms/outputs.tf" \
    "modules/platform-cluster-vms/versions.tf" \
    "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl"; do
    assert_file_exists "$file"
  done
}

assert_vms_module_variables_documented() {
  local variables_file="${INFRA_DIR}/modules/platform-cluster-vms/variables.tf"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "platform-cluster-vms variables documented"
    return
  fi

  if "$PYTHON_BIN" - "$variables_file" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
expected = {
    "channel_id",
    "cluster_name",
    "region",
    "vpc_id",
    "k3s_version",
    "server_count",
    "server_plan",
    "agent_count",
    "agent_plan",
    "os_id",
    "ssh_key_ids",
}

blocks = {}
for match in re.finditer(r'variable\s+"([^"]+)"\s+\{', text):
    name = match.group(1)
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    blocks[name] = text[start:index - 1]

missing = expected - blocks.keys()
extra = blocks.keys() - expected
if missing or extra:
    raise SystemExit(f"variable set mismatch: missing={sorted(missing)} extra={sorted(extra)}")

for name in sorted(expected):
    block = blocks[name]
    if not re.search(r"^\s*type\s*=", block, re.MULTILINE):
        raise SystemExit(f"{name} missing type")
    has_default = re.search(r"^\s*default\s*=", block, re.MULTILINE) is not None
    description_match = re.search(r'^\s*description\s*=\s*"([^"]+)"', block, re.MULTILINE)
    if not description_match:
        raise SystemExit(f"{name} missing description")
    if not has_default and not description_match.group(1).endswith("no default; required"):
        raise SystemExit(f"{name} missing required-description suffix")
PY
  then
    pass "platform-cluster-vms variables documented"
  else
    fail "platform-cluster-vms variables documented"
  fi

  assert_file_contains "modules/platform-cluster-vms/outputs.tf" "sensitive = true" "platform-cluster-vms sensitive token output"
}

assert_cloud_init_template_present() {
  assert_file_exists "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl"
}

assert_cloud_init_idempotency_marker() {
  assert_file_contains "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl" "/etc/k3s-install-marker" "cloud-init idempotency marker"
}

assert_cloud_init_strict_failure() {
  assert_file_contains "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl" "set -euo pipefail" "cloud-init strict shell flags"
  assert_file_contains "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl" "exit 1" "cloud-init explicit failure exits"
}

assert_template_has_conditional_dispatch() {
  assert_file_contains "templates/platform-channel/main.tf" 'count  = var.cluster_target == "k3d-local"' "template dispatches k3d-local"
  assert_file_contains "templates/platform-channel/main.tf" 'count  = var.cluster_target == "vultr-vms"' "template dispatches vultr-vms"
}

assert_dev_root_present() {
  for file in \
    "roots/channels/dev/main.tf" \
    "roots/channels/dev/backend.tfbackend" \
    "roots/channels/dev/channel.auto.tfvars.json" \
    "roots/channels/dev/.terraform.lock.hcl"; do
    assert_file_exists "$file"
  done
}

assert_dev_tofu_validate() {
  local root="${INFRA_DIR}/roots/channels/dev"
  local lockfile="${root}/.terraform.lock.hcl"
  local before
  local after

  if ! command -v tofu >/dev/null 2>&1; then
    fail "dev root tofu validate"
    return
  fi

  before="$(sha256sum "$lockfile" | awk '{print $1}')"

  if tofu -chdir="$root" init -backend=false >/dev/null && tofu -chdir="$root" validate >/dev/null; then
    pass "dev root tofu init -backend=false and validate"
  else
    fail "dev root tofu init -backend=false and validate"
    return
  fi

  after="$(sha256sum "$lockfile" | awk '{print $1}')"
  if [[ "$before" == "$after" ]]; then
    pass "dev root lockfile byte-identical after re-init"
  else
    fail "dev root lockfile byte-identical after re-init"
  fi
}

assert_local_root_present() {
  for file in \
    "roots/channels/local/main.tf" \
    "roots/channels/local/backend.tfbackend" \
    "roots/channels/local/channel.auto.tfvars.json" \
    "roots/channels/local/.terraform.lock.hcl"; do
    assert_file_exists "$file"
  done
}

assert_channel_backend_drift_check() {
  local channel="$1"
  local committed="${INFRA_DIR}/roots/channels/${channel}/backend.tfbackend"
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/${channel}"
  local resolved="${tmp_dir}/resolved.json"
  local generated="${tmp_dir}/backend.tfbackend"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "${channel} backend generator drift check"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" --out "$resolved" \
    && "$PYTHON_BIN" "${INFRA_DIR}/scripts/generate_channel_backend.py" --resolved "$resolved" --out "$generated" \
    && cmp -s "$generated" "$committed"; then
    pass "${channel} backend generated artifact drift-free"
  else
    diff -u "$committed" "$generated" || true
    fail "${channel} backend generated artifact drift-free"
  fi
}

assert_channel_tfvars_drift_check() {
  local channel="$1"
  local committed="${INFRA_DIR}/roots/channels/${channel}/channel.auto.tfvars.json"
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/${channel}"
  local resolved="${tmp_dir}/resolved.json"
  local generated="${tmp_dir}/channel.auto.tfvars.json"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "${channel} tfvars generator drift check"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" --out "$resolved" \
    && "$PYTHON_BIN" "${INFRA_DIR}/scripts/generate_channel_tfvars.py" --resolved "$resolved" --out "$generated" \
    && cmp -s "$generated" "$committed"; then
    pass "${channel} tfvars generated artifact drift-free"
  else
    diff -u "$committed" "$generated" || true
    fail "${channel} tfvars generated artifact drift-free"
  fi
}

assert_local_tofu_validate() {
  local root="${INFRA_DIR}/roots/channels/local"
  local lockfile="${root}/.terraform.lock.hcl"
  local before
  local after

  if ! command -v tofu >/dev/null 2>&1; then
    fail "local root tofu validate"
    return
  fi

  before="$(sha256sum "$lockfile" | awk '{print $1}')"

  if tofu -chdir="$root" init -backend=false >/dev/null && tofu -chdir="$root" validate >/dev/null; then
    pass "local root tofu init -backend=false and validate"
  else
    fail "local root tofu init -backend=false and validate"
    return
  fi

  after="$(sha256sum "$lockfile" | awk '{print $1}')"
  if [[ "$before" == "$after" ]]; then
    pass "local root lockfile byte-identical after re-init"
  else
    fail "local root lockfile byte-identical after re-init"
  fi
}

assert_spawn_against_dev_succeeds() {
  local out_dir="${REPO_ROOT}/.tmp/test-spawn"
  local output_file="${out_dir}/channel.yaml"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "spawn against dev succeeds"
    return
  fi

  rm -rf "$out_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/spawn_platform_channel.py" --parent dev --suffix pr-123 --out .tmp/test-spawn \
    && [[ -f "$output_file" ]] \
    && grep -q '^id: dev-pr-123$' "$output_file" \
    && [[ ! -e "${INFRA_DIR}/channels/dev-pr-123.yaml" ]] \
    && [[ ! -e "${INFRA_DIR}/roots/channels/dev-pr-123" ]]; then
    pass "spawn against dev succeeds under .tmp only"
  else
    fail "spawn against dev succeeds under .tmp only"
  fi
}

assert_spawn_against_disabled_fails() {
  local out_dir="${REPO_ROOT}/.tmp/test-spawn-disabled"
  local output
  local status

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "spawn against disabled channel fails"
    return
  fi

  rm -rf "$out_dir"
  set +e
  output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/spawn_platform_channel.py" --parent ephemeral-disabled --suffix pr-123 --out .tmp/test-spawn-disabled 2>&1)"
  status=$?
  set -e

  if [[ "$status" -ne 0 ]] && grep -q '"code": "ephemeral_children_disabled"' <<<"$output" && [[ ! -e "$out_dir/channel.yaml" ]]; then
    pass "spawn against disabled channel returns structured failure"
  else
    fail "spawn against disabled channel returns structured failure"
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

  if k3d cluster get humility-local >/dev/null 2>&1; then
    skip "delete-local-channel missing-cluster check skipped because humility-local exists"
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
  local bring_up_output
  local second_bring_up_output
  local delete_output
  local second_delete_output
  local bring_up_status
  local second_bring_up_status
  local delete_status
  local second_delete_status

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

  set +e
  bring_up_output="$(bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local 2>&1)"
  bring_up_status=$?
  set -e

  if [[ "$bring_up_status" -eq 0 ]]; then
    CLUSTER_EXERCISED=1
    pass "local k3d cluster bring-up"
  else
    echo "$bring_up_output"
    fail "local k3d cluster bring-up"
    return
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    pass "local kubeconfig exists"
  else
    fail "local kubeconfig exists"
  fi

  if node_count="$(kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null | awk 'NF { count += 1 } END { print count + 0 }')" && [[ "$node_count" -ge 1 ]]; then
    pass "kubectl get nodes returns ${node_count} node(s)"
  else
    fail "kubectl get nodes returns at least one node"
  fi

  if kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null | awk 'NF && $2 != "Ready" { bad = 1 } END { exit bad }'; then
    pass "kubectl get nodes reports all nodes Ready"
  else
    fail "kubectl get nodes reports all nodes Ready"
  fi

  set +e
  second_bring_up_output="$(bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local 2>&1)"
  second_bring_up_status=$?
  set -e

  if [[ "$second_bring_up_status" -eq 0 ]] && grep -q "already up; no changes needed" <<<"$second_bring_up_output"; then
    pass "second bring-up is an idempotent no-op"
  else
    echo "$second_bring_up_output"
    fail "second bring-up is an idempotent no-op"
  fi

  set +e
  delete_output="$(bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local 2>&1)"
  delete_status=$?
  set -e

  if [[ "$delete_status" -eq 0 ]]; then
    pass "local k3d cluster cleanup"
  else
    echo "$delete_output"
    fail "local k3d cluster cleanup"
  fi

  if ! k3d cluster get humility-local >/dev/null 2>&1; then
    pass "local k3d cluster gone after cleanup"
  else
    fail "local k3d cluster gone after cleanup"
  fi

  set +e
  second_delete_output="$(bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local 2>&1)"
  second_delete_status=$?
  set -e

  if [[ "$second_delete_status" -eq 0 ]] && grep -q "already gone" <<<"$second_delete_output"; then
    pass "second delete is an idempotent no-op"
  else
    echo "$second_delete_output"
    fail "second delete is an idempotent no-op"
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
echo "=== Slice 101.03 remote Vultr VM plan-surface validation ==="

assert_vms_module_present
assert_vms_module_variables_documented
assert_cloud_init_template_present
assert_cloud_init_idempotency_marker
assert_cloud_init_strict_failure
assert_template_has_conditional_dispatch
assert_dev_root_present
assert_dev_tofu_validate

echo ""
echo "=== Slice 101.04 channel template and generated root validation ==="

for file in \
  "scripts/generate_channel_backend.py" \
  "scripts/generate_channel_tfvars.py" \
  "scripts/spawn_platform_channel.py"; do
  assert_file_exists "$file"
  assert_executable "$file"
done

assert_local_root_present
assert_channel_backend_drift_check "dev"
assert_channel_tfvars_drift_check "dev"
assert_channel_backend_drift_check "local"
assert_channel_tfvars_drift_check "local"
assert_local_tofu_validate
assert_spawn_against_dev_succeeds
assert_spawn_against_disabled_fails

echo ""
echo "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
if [[ "$CLUSTER_EXERCISED" -eq 1 ]]; then
  echo "Cluster mode exercised: yes"
else
  echo "Cluster mode exercised: no"
fi

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
