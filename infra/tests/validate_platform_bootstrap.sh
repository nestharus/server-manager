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

assert_repo_path_absent() {
  local path="$1"
  if [[ ! -e "${REPO_ROOT}/${path}" ]]; then
    pass "absent: ${path}"
  else
    fail "still exists: ${path}"
  fi
}

assert_repo_file_exists() {
  local file="$1"
  if [[ -f "${REPO_ROOT}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "missing: ${file}"
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

assert_sops_bootstrap_boundary() {
  local sops_config="${REPO_ROOT}/.sops.yaml"
  local sentinel="${REPO_ROOT}/gitops/bootstrap/sops-sentinel.enc.yaml"
  local linter="${INFRA_DIR}/scripts/lint-sops-boundary.py"
  local py_bin

  assert_repo_file_exists ".sops.yaml"

  if ! py_bin="$(python_bin)"; then
    fail ".sops.yaml creation rule"
  elif "$py_bin" - "$sops_config" <<'PY'
import sys
from pathlib import Path

import yaml

data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
rules = data.get("creation_rules") if isinstance(data, dict) else None
if not isinstance(rules, list) or len(rules) != 1:
    raise SystemExit("expected exactly one creation_rule")
rule = rules[0]
if rule.get("path_regex") != r"^gitops/bootstrap/.*\.enc\.yaml$":
    raise SystemExit("creation_rule path_regex mismatch")
if rule.get("encrypted_regex") != "^(data|stringData)$":
    raise SystemExit("creation_rule encrypted_regex mismatch")
age = rule.get("age")
if not isinstance(age, str) or not age.startswith("age1"):
    raise SystemExit("creation_rule age recipient missing")
PY
  then
    pass ".sops.yaml creation rule"
  else
    fail ".sops.yaml creation rule"
  fi

  assert_repo_file_exists "gitops/bootstrap/sops-sentinel.enc.yaml"
  if [[ -f "$sentinel" ]] && grep -q '^sops:' "$sentinel" && grep -q '^[[:space:]]*mac:' "$sentinel"; then
    pass "sops sentinel is encrypted"
  else
    fail "sops sentinel is encrypted"
  fi

  if [[ -n "${py_bin:-}" && -f "$linter" ]] && "$py_bin" "$linter" >/dev/null; then
    pass "SOPS boundary lint"
  else
    fail "SOPS boundary lint"
  fi

  assert_file_exists "scripts/bootstrap-sops-age-key.sh"
  assert_executable "scripts/bootstrap-sops-age-key.sh"
}

assert_gitops_channel_schema_rendering() {
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/gitops"
  local local_resolved="${tmp_dir}/local.resolved.json"
  local dev_resolved="${tmp_dir}/dev.resolved.json"
  local out_dir="${REPO_ROOT}/.tmp/gitops-source/local"
  local before
  local after
  local render_status
  local rerender_status
  local py_bin

  if ! py_bin="$(python_bin)"; then
    fail "python interpreter available for GitOps rendering"
    return
  fi

  rm -rf "$tmp_dir" "${REPO_ROOT}/.tmp/gitops-source"
  mkdir -p "$tmp_dir"

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel local --out "$local_resolved" \
    && "$py_bin" - "$local_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "source_kind": "git",
    "git_url": "http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git",
    "git_ref": "refs/heads/main",
    "path": "./gitops/channels/local",
    "kustomization_name": "humility-local",
    "kustomization_namespace": "flux-system",
    "sops_age_secret_name": "sops-age",
    "decryption_secret_namespace": "flux-system",
    "interval": "1m",
    "retry_interval": "1m",
    "prune": True,
    "wait": True,
}
if data.get("gitops") != expected:
    raise SystemExit(f"unexpected gitops block: {data.get('gitops')!r}")
PY
  then
    pass "local channel resolves with operator-supplied gitops block"
  else
    fail "local channel resolves with operator-supplied gitops block"
  fi

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$dev_resolved" \
    && "$py_bin" - "$dev_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if "gitops" in data:
    raise SystemExit("dev must omit gitops in INIT-102")
PY
  then
    pass "dev channel validates without gitops block"
  else
    fail "dev channel validates without gitops block"
  fi

  set +e
  "$py_bin" "${INFRA_DIR}/scripts/render-gitops-source.py" --channel local --out "$out_dir" >/dev/null
  render_status=$?
  set -e

  if [[ "$render_status" -eq 0 ]]; then
    pass "render-gitops-source local exits 0"
  else
    fail "render-gitops-source local exits 0"
    return
  fi

  for file in \
    "gitops/sources/local/gitrepository.yaml" \
    "gitops/sources/local/kustomization.yaml" \
    "gitops/sources/local/kustomization.kustomize.yaml" \
    "gitops/channels/local/generated/gitops-snapshot-marker.yaml"; do
    if [[ -f "${out_dir}/${file}" ]]; then
      pass "rendered: ${file}"
    else
      fail "missing rendered file: ${file}"
    fi
  done

  before="$(find "$out_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"
  set +e
  "$py_bin" "${INFRA_DIR}/scripts/render-gitops-source.py" --channel local --out "$out_dir" >/dev/null
  rerender_status=$?
  set -e
  after="$(find "$out_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"

  if [[ "$rerender_status" -eq 0 && "$before" == "$after" ]]; then
    pass "render-gitops-source is byte-identical on rerun"
  else
    fail "render-gitops-source is byte-identical on rerun"
  fi
}

assert_gitops_flux_components() {
  local file="${REPO_ROOT}/gitops/flux/gotk-components.yaml"
  local deployment_count
  local unexpected_deployment_count

  if [[ -f "$file" ]]; then
    pass "exists: gitops/flux/gotk-components.yaml"
  else
    fail "missing: gitops/flux/gotk-components.yaml"
    return
  fi

  deployment_count="$(grep -c '^kind: Deployment$' "$file" || true)"
  if [[ "$deployment_count" == "2" ]]; then
    pass "Flux lockfile has exactly 2 Deployments"
  else
    fail "Flux lockfile has exactly 2 Deployments"
  fi

  if awk 'BEGIN { RS = "---"; found = 0 } /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*source-controller/ { found = 1 } END { exit found ? 0 : 1 }' "$file"; then
    pass "Flux lockfile includes source-controller Deployment"
  else
    fail "Flux lockfile includes source-controller Deployment"
  fi

  if awk 'BEGIN { RS = "---"; found = 0 } /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*kustomize-controller/ { found = 1 } END { exit found ? 0 : 1 }' "$file"; then
    pass "Flux lockfile includes kustomize-controller Deployment"
  else
    fail "Flux lockfile includes kustomize-controller Deployment"
  fi

  unexpected_deployment_count="$(
    awk '
      BEGIN { RS = "---"; count = 0 }
      /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*(helm-controller|notification-controller|image-reflector-controller|image-automation-controller)/ {
        count += 1
      }
      END { print count }
    ' "$file"
  )"
  if [[ "$unexpected_deployment_count" == "0" ]]; then
    pass "Flux lockfile excludes helm/notification/image controller Deployments"
  else
    fail "Flux lockfile excludes helm/notification/image controller Deployments"
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
    "region",
    "vpc_id",
    "k3s_version",
    "server_count",
    "server_plan",
    "agent_count",
    "agent_plan",
    "ssh_key_ids",
    "allowed_ssh_cidrs",
    "remote_kubeconfig_path",
    "firewall_name",
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

assert_tool_version() {
  local tool="$1"
  local expected="$2"
  local pattern="$3"
  local raw_output
  local output
  local status

  set +e
  raw_output="$("$tool" --version 2>&1)"
  status=$?
  set -e
  output="$(sed -n '1p' <<<"$raw_output")"

  if [[ "$status" -eq 0 ]] && grep -Eq "$pattern" <<<"$output"; then
    pass "${tool} --version returns ${expected} (${output//$'\n'/; })"
  else
    fail "${tool} --version returns ${expected} (${output//$'\n'/; })"
  fi
}

assert_command_version() {
  local description="$1"
  local expected="$2"
  local pattern="$3"
  shift 3
  local raw_output
  local output
  local status

  set +e
  raw_output="$("$@" 2>&1)"
  status=$?
  set -e
  output="$(sed -n '1p' <<<"$raw_output")"

  if [[ "$status" -eq 0 ]] && grep -Eq "$pattern" <<<"$output"; then
    pass "${description} returns ${expected} (${output//$'\n'/; })"
  else
    fail "${description} returns ${expected} (${output//$'\n'/; })"
  fi
}

assert_gitops_tool_versions() {
  assert_tool_version "flux" "v2.8.6" '^flux version 2\.8\.6$'
  assert_command_version "helm version --short" "v3.20.2" '^v3\.20\.2(\+.*)?$' helm version --short
  assert_tool_version "sops" "v3.12.2" '^sops 3\.12\.2([[:space:]].*)?$'
  assert_tool_version "age" "v1.3.1" '^v1\.3\.1$'
  assert_tool_version "age-keygen" "v1.3.1" '^v1\.3\.1$'
  assert_tool_version "infisical" "infisical version 0.43.78" '^infisical version 0\.43\.78$'
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
  local marker_file="${REPO_ROOT}/.tmp/gitops-source/local/gitops/channels/local/generated/gitops-snapshot-marker.yaml"
  local expected_sha
  local actual_sha
  local git_pod
  local git_snapshot_ok
  local attempt

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

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "Flux GitRepository status=Ready"
  else
    fail "Flux GitRepository status=Ready"
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "Flux Kustomization status=Ready"
  else
    fail "Flux Kustomization status=Ready"
  fi

  echo "Flux resources after bring-up:"
  kubectl --kubeconfig "$kubeconfig_path" get gitrepository,kustomization -A || true

  expected_sha="$(awk '/^[[:space:]]*source_sha:/ { print $2; exit }' "$marker_file" 2>/dev/null || true)"
  actual_sha="$(kubectl --kubeconfig "$kubeconfig_path" -n humility-gitops-sentinel get configmap gitops-snapshot-marker -o jsonpath='{.data.source_sha}' 2>/dev/null || true)"
  if [[ -n "$expected_sha" && "$actual_sha" == "$expected_sha" ]]; then
    pass "snapshot SHA marker reached cluster (${actual_sha})"
  else
    fail "snapshot SHA marker reached cluster"
  fi

  git_pod="$(kubectl --kubeconfig "$kubeconfig_path" -n git-system get pod -l app.kubernetes.io/name=git-daemon --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  if [[ -n "$git_pod" ]] \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system delete pod "$git_pod" --wait=false >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system rollout status deployment/git-daemon --timeout=180s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system wait deployment/git-daemon --for=condition=Available --timeout=180s >/dev/null; then
    pass "git-daemon Deployment recreates Pod after deletion"
  else
    fail "git-daemon Deployment recreates Pod after deletion"
  fi

  git_snapshot_ok=0
  for attempt in $(seq 1 60); do
    git_pod="$(kubectl --kubeconfig "$kubeconfig_path" -n git-system get pod -l app.kubernetes.io/name=git-daemon --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -n "$git_pod" ]] \
      && kubectl --kubeconfig "$kubeconfig_path" -n git-system exec "$git_pod" -c git-daemon -- git --git-dir=/srv/git/humility-local.git rev-parse --verify refs/heads/main >/dev/null 2>&1; then
      git_snapshot_ok=1
      break
    fi
    sleep 2
  done

  if [[ "$git_snapshot_ok" -eq 1 ]]; then
    pass "git-daemon PVC preserves seeded snapshot after Pod restart"
  else
    fail "git-daemon PVC preserves seeded snapshot after Pod restart"
  fi

  if command -v flux >/dev/null 2>&1; then
    KUBECONFIG="$kubeconfig_path" flux reconcile source git humility-local --namespace flux-system --timeout=180s >/dev/null 2>&1 || true
    KUBECONFIG="$kubeconfig_path" flux reconcile kustomization humility-local --namespace flux-system --with-source --timeout=180s >/dev/null 2>&1 || true
  else
    kubectl --kubeconfig "$kubeconfig_path" -n flux-system annotate gitrepository/humility-local reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite >/dev/null 2>&1 || true
    kubectl --kubeconfig "$kubeconfig_path" -n flux-system annotate kustomization/humility-local reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite >/dev/null 2>&1 || true
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=180s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "git-daemon restart resilience: Flux still reconciles"
  else
    fail "git-daemon restart resilience: Flux still reconciles"
  fi

  set +e
  second_bring_up_output="$(bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local 2>&1)"
  second_bring_up_status=$?
  set -e

  if [[ "$second_bring_up_status" -eq 0 ]] && grep -q "Flux post-install complete for channel 'local'" <<<"$second_bring_up_output"; then
    pass "second bring-up reapplies Flux without error"
  else
    echo "$second_bring_up_output"
    fail "second bring-up reapplies Flux without error"
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
  "scripts/install-flux-for-channel.sh" \
  "scripts/delete-local-channel.sh"; do
  assert_file_exists "$file"
done

assert_dir_exists "modules/platform-cluster-k3d"
assert_executable "scripts/install-cluster-tools.sh"
assert_executable "scripts/bring-up-local-channel.sh"
assert_executable "scripts/install-flux-for-channel.sh"
assert_executable "scripts/delete-local-channel.sh"
assert_install_cluster_tools_check
assert_gitops_tool_versions
assert_bring_up_script_help_works
assert_delete_missing_local_cluster

echo ""
echo "=== Slice 102.02 GitOps layout and Flux lockfile validation ==="

assert_gitops_flux_components
assert_repo_path_absent "k8s"
assert_repo_file_exists "gitops/sources/local/git-daemon.yaml"
assert_file_exists "scripts/render-gitops-source.py"
assert_executable "scripts/render-gitops-source.py"
assert_gitops_channel_schema_rendering

echo ""
echo "=== Slice 102.03 SOPS+age bootstrap sentinel validation ==="

assert_sops_bootstrap_boundary

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
