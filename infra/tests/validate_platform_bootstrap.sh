#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0
BACKEND_DRIFT_OK=false
TFVARS_DRIFT_OK=false

pass() {
  echo "  PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

section() {
  echo ""
  echo "=== $1 ==="
}

assert_file_exists() {
  local file="$1"
  if [[ -f "${INFRA_DIR}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "exists: ${file}"
  fi
}

assert_environments_dir_gone() {
  if [[ ! -d "${INFRA_DIR}/environments" ]]; then
    pass "infra/environments removed"
  else
    fail "infra/environments removed"
  fi
}

assert_tofu_version_111() {
  local first_line

  if ! command -v tofu >/dev/null 2>&1; then
    fail "OpenTofu CLI is installed"
    return
  fi

  tofu version
  first_line="$(tofu version | head -1)"
  if grep -Eq '^OpenTofu v1\.11\.[0-9]+' <<<"$first_line"; then
    pass "OpenTofu major.minor is 1.11"
  else
    fail "OpenTofu major.minor is 1.11"
  fi
}

assert_grep() {
  local pattern="$1"
  local file="${INFRA_DIR}/$2"
  local label="$3"
  if grep -qE "$pattern" "$file" 2>/dev/null; then
    pass "$label"
  else
    fail "$label"
  fi
}

assert_no_grep() {
  local pattern="$1"
  local file="${INFRA_DIR}/$2"
  local label="$3"
  if grep -qE "$pattern" "$file" 2>/dev/null; then
    fail "$label"
  else
    pass "$label"
  fi
}

assert_rg_match() {
  local pattern="$1"
  local path="${INFRA_DIR}/$2"
  local label="$3"
  if rg -n "$pattern" "$path" >/dev/null; then
    pass "$label"
  else
    fail "$label"
  fi
}

assert_rg_no_match() {
  local pattern="$1"
  local path="${INFRA_DIR}/$2"
  local label="$3"
  local status
  if [[ ! -e "$path" ]]; then
    fail "${label} (path does not exist: ${path})"
    return
  fi
  set +e
  rg -n "$pattern" "$path" >/dev/null
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    fail "$label"
  elif [[ "$status" -eq 1 ]]; then
    pass "$label"
  else
    fail "${label} (rg failed with status ${status})"
  fi
}

assert_bootstrap_no_bucket_resource() {
  local bucket_resource_pattern
  bucket_resource_pattern="$(printf '%s%s' 'vultr_object_storage_' 'bucket')"
  if rg -n "$bucket_resource_pattern" \
    "${INFRA_DIR}/bootstrap/state-backend" \
    "${INFRA_DIR}/tests" >/dev/null; then
    fail "bootstrap and harness contain no managed object-storage bucket resource"
  else
    pass "bootstrap and harness contain no managed object-storage bucket resource"
  fi
}

assert_bootstrap_outputs_sensitive() {
  local file="${INFRA_DIR}/bootstrap/state-backend/main.tf"
  local ok=true

  if ! grep -A4 'output\s*"s3_access_key"' "$file" | grep -q 'sensitive\s*=\s*true'; then
    ok=false
  fi
  if ! grep -A4 'output\s*"s3_secret_key"' "$file" | grep -q 'sensitive\s*=\s*true'; then
    ok=false
  fi

  if [[ "$ok" == true ]]; then
    pass "bootstrap S3 access and secret outputs are sensitive"
  else
    fail "bootstrap S3 access and secret outputs are sensitive"
  fi
}

assert_dev_backend_key() {
  if rg -n 'channels/dev/terraform\.tfstate' "${INFRA_DIR}/roots/channels/dev/backend.tfbackend" >/dev/null; then
    pass "dev backend key is channels/dev/terraform.tfstate"
  else
    fail "dev backend key is channels/dev/terraform.tfstate"
  fi
}

assert_no_credentials_in_dev_backend() {
  if rg -n 'access_key|secret_key' "${INFRA_DIR}/roots/channels/dev/backend.tfbackend" >/dev/null; then
    fail "dev backend contains no access_key or secret_key entries"
  else
    pass "dev backend contains no access_key or secret_key entries"
  fi
}

assert_no_endpoint_in_dev_backend() {
  if rg -n '^endpoint\s*=' "${INFRA_DIR}/roots/channels/dev/backend.tfbackend" >/dev/null; then
    fail "dev backend contains no endpoint entry"
  else
    pass "dev backend contains no endpoint entry"
  fi
}

assert_readme_documents_locking_posture() {
  local file="${INFRA_DIR}/README.md"
  if rg -nq 'locking' "$file" \
    && rg -nq 'restore' "$file" \
    && rg -nq 'single-operator|single operator' "$file" \
    && rg -nq 'object-storage versioning|Object Storage versioning' "$file" \
    && rg -nq 'post-Phase-5 deployment initiative' "$file"; then
    pass "README documents bounded locking and restore posture"
  else
    fail "README documents bounded locking and restore posture"
  fi
}

assert_readme_documents_optional_provider_plan() {
  local file="${INFRA_DIR}/README.md"
  if rg -nq 'Provider-backed plan runbook \(optional\)' "$file" \
    && rg -nq 'INIT-008 baseline verification works without' "$file" \
    && rg -nq 'tofu plan' "$file" \
    && rg -nq 'VULTR_API_KEY' "$file" \
    && rg -nq 'OBJECT_STORAGE_HOSTNAME' "$file"; then
    pass "README documents optional provider-backed dev plan runbook"
  else
    fail "README documents optional provider-backed dev plan runbook"
  fi
}

assert_readme_apply_is_out_of_scope() {
  local file="${INFRA_DIR}/README.md"
  if rg -nq 'must not be followed' "$file" \
    && rg -nq '`tofu apply` in INIT-008 scope' "$file" \
    && rg -nq '`tofu apply` is out-of-scope for Phase 5' "$file" \
    && ! rg -nq '`tofu apply` as verification|tofu apply as verification' "$file"; then
    pass "README frames tofu apply only as out-of-scope"
  else
    fail "README frames tofu apply only as out-of-scope"
  fi
}

assert_no_endpoint_placeholder() {
  if rg -n 'endpoint placeholder|REPLACE_AFTER_BOOTSTRAP' \
    "${INFRA_DIR}/channels" \
    "${INFRA_DIR}/schemas" \
    "${INFRA_DIR}/roots" >/dev/null; then
    fail "no endpoint placeholder remains under channels, schemas, or roots"
  else
    pass "no endpoint placeholder remains under channels, schemas, or roots"
  fi
}

assert_readme_documents_retirement() {
  if rg -nq 'retire|retirement' "${INFRA_DIR}/README.md"; then
    pass "README documents channel retirement"
  else
    fail "README documents channel retirement"
  fi
}

assert_recursive_fmt_check() {
  if (cd "$REPO_ROOT" && tofu fmt -check -recursive infra/ >/dev/null); then
    pass "recursive tofu fmt -check for infra"
  else
    fail "recursive tofu fmt -check for infra"
  fi
}

assert_bootstrap_tofu_validate() {
  if (cd "${INFRA_DIR}/bootstrap/state-backend" && tofu fmt -check >/dev/null); then
    pass "bootstrap tofu fmt -check"
  else
    fail "bootstrap tofu fmt -check"
    return
  fi

  assert_tofu_root_validates "bootstrap/state-backend" true
}

assert_json_value() {
  local file="$1"
  local dotted_path="$2"
  local expected="$3"
  local label="$4"

  if python3 - "$file" "$dotted_path" "$expected" <<'PY'
import json
import sys

path, dotted_path, expected = sys.argv[1:]
with open(path, "r", encoding="utf-8") as handle:
    value = json.load(handle)
for part in dotted_path.split("."):
    value = value[part]
if str(value) != expected:
    raise SystemExit(f"{dotted_path}: expected {expected!r}, got {value!r}")
PY
  then
    pass "$label"
  else
    fail "$label"
  fi
}

assert_no_active_retired_provider_references() {
  local label="active docs contain no retired provider/self-managed cluster references"
  local pattern
  pattern="$(printf '%s|%s|%s' 'He''tz''ner' 'kube-''he''tz''ner' 'k''3''s')"
  local files=(
    "${REPO_ROOT}/DECISIONS.md"
    "${REPO_ROOT}/plans/platform-decisions-overlay.md"
    "${REPO_ROOT}/.pipeline/proposal.md"
    "${REPO_ROOT}/infra/README.md"
  )

  local found=false
  for file in "${files[@]}"; do
    if [[ -f "$file" ]] && grep -qiE "$pattern" "$file"; then
      found=true
    fi
  done

  while IFS= read -r -d '' file; do
    if grep -qiE "$pattern" "$file"; then
      found=true
    fi
  done < <(find "${INFRA_DIR}" -type f -print0)

  if [[ "$found" == true ]]; then
    fail "$label"
  else
    pass "$label"
  fi
}

assert_decisions_d7_present() {
  if grep -q '## D7 — 2026-04-25 — Ratify Vultr' "${REPO_ROOT}/DECISIONS.md"; then
    pass "DECISIONS.md contains D7 Vultr/OpenTofu/channel pivot"
  else
    fail "DECISIONS.md contains D7 Vultr/OpenTofu/channel pivot"
  fi
}

assert_dev_tofu_fmt_check() {
  if (cd "${INFRA_DIR}/roots/channels/dev" && tofu fmt -check >/dev/null); then
    pass "dev channel root tofu fmt -check"
  else
    fail "dev channel root tofu fmt -check"
  fi
}

assert_tofu_root_validates() {
  local root="$1"
  local preserve_lockfile="${2:-false}"
  local root_dir="${INFRA_DIR}/${root}"

  if (cd "$root_dir" && tofu init -backend=false >/dev/null); then
    pass "tofu init -backend=false: ${root}"
  else
    fail "tofu init -backend=false: ${root}"
    return
  fi

  if (cd "$root_dir" && tofu validate >/dev/null); then
    pass "tofu validate: ${root}"
  else
    fail "tofu validate: ${root}"
  fi

  rm -rf "${root_dir}/.terraform"
  if [[ "$preserve_lockfile" != true ]]; then
    rm -f "${root_dir}/.terraform.lock.hcl"
  fi
}

assert_template_variables_documented() {
  if python3 - "${INFRA_DIR}/templates/platform-channel/variables.tf" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
blocks = re.findall(r'variable\s+"([^"]+)"\s*\{(.*?)\n\}', text, re.S)
if not blocks:
    raise SystemExit("no variable blocks found")

missing = []
for name, body in blocks:
    has_type = re.search(r'^\s*type\s*=', body, re.M) is not None
    has_default = re.search(r'^\s*default\s*=', body, re.M) is not None
    has_required_description = re.search(
        r'^\s*description\s*=\s*"[^"]*no default; required"\s*$',
        body,
        re.M,
    ) is not None
    if not has_type or not (has_default or has_required_description):
        missing.append(name)

if missing:
    raise SystemExit(", ".join(missing))
PY
  then
    pass "template variables have type and default-or-required contract"
  else
    fail "template variables have type and default-or-required contract"
  fi
}

assert_backend_drift_check() {
  local resolved="${REPO_ROOT}/.tmp/dev.resolved.json"
  local generated="${REPO_ROOT}/.tmp/dev.backend.tfbackend"

  if python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$resolved" \
    && python3 "${INFRA_DIR}/scripts/generate_channel_backend.py" --resolved "$resolved" --out "$generated" \
    && cmp -s "$generated" "${INFRA_DIR}/roots/channels/dev/backend.tfbackend"; then
    BACKEND_DRIFT_OK=true
    pass "backend.tfbackend regenerates byte-identically"
  else
    fail "backend.tfbackend regenerates byte-identically"
  fi
}

assert_tfvars_drift_check() {
  local resolved="${REPO_ROOT}/.tmp/dev.resolved.json"
  local generated="${REPO_ROOT}/.tmp/dev.channel.auto.tfvars.json"
  local committed="${INFRA_DIR}/roots/channels/dev/channel.auto.tfvars.json"

  if python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$resolved" \
    && python3 "${INFRA_DIR}/scripts/generate_channel_tfvars.py" --resolved "$resolved" --out "$generated" \
    && python3 - "$generated" "$committed" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as generated_handle:
    generated = json.load(generated_handle)
with open(sys.argv[2], "r", encoding="utf-8") as committed_handle:
    committed = json.load(committed_handle)
if generated != committed:
    raise SystemExit("generated tfvars differ from committed tfvars")
PY
  then
    TFVARS_DRIFT_OK=true
    pass "channel.auto.tfvars.json regenerates structurally identically"
  else
    fail "channel.auto.tfvars.json regenerates structurally identically"
  fi
}

assert_generated_artifacts_covered() {
  if [[ "$BACKEND_DRIFT_OK" == true && "$TFVARS_DRIFT_OK" == true ]]; then
    pass "all dev generated artifacts have drift checks"
  else
    fail "all dev generated artifacts have drift checks"
  fi
}

assert_no_committed_credentials_in_tf() {
  local pattern='\b(access_key|secret_key|password|api_key)\b\s*=\s*"[^"$][^"]*"'

  if rg -n -i --type-add 'tf:*.tf' --type tf "$pattern" "${INFRA_DIR}" >/dev/null; then
    fail "no committed credential assignments in .tf files"
  else
    pass "no committed credential assignments in .tf files"
  fi
}

assert_no_committed_credentials_in_tfbackend() {
  local files=()
  local path

  while IFS= read -r path; do
    files+=("$path")
  done < <(compgen -G "${INFRA_DIR}/roots/channels/*/backend.tfbackend" || true)

  while IFS= read -r path; do
    files+=("$path")
  done < <(compgen -G "${INFRA_DIR}/bootstrap/*/backend.tfbackend" || true)

  if [[ "${#files[@]}" -eq 0 ]]; then
    pass "no committed credentials in .tfbackend files"
    return
  fi

  if rg -n -i '(access_key|secret_key)' "${files[@]}" >/dev/null; then
    fail "no committed credentials in .tfbackend files"
  else
    pass "no committed credentials in .tfbackend files"
  fi
}

assert_no_committed_credentials_in_yaml() {
  if rg -n -i '(access_key|secret_key|password|api_key|token)\s*:' \
    "${INFRA_DIR}/channels" \
    "${INFRA_DIR}/schemas" >/dev/null; then
    fail "no committed credential keys in channel or schema YAML"
  else
    pass "no committed credential keys in channel or schema YAML"
  fi
}

assert_no_committed_credentials_in_active_tfvars() {
  local files=()
  local path

  while IFS= read -r path; do
    files+=("$path")
  done < <(compgen -G "${INFRA_DIR}/roots/channels/*/channel.auto.tfvars.json" || true)

  if [[ "${#files[@]}" -eq 0 ]]; then
    fail "active channel tfvars files exist for credential scan"
    return
  fi

  if rg -n -i '(access_key|secret_key|password|api_key)' "${files[@]}" >/dev/null; then
    fail "no committed credentials in active channel tfvars"
  else
    pass "no committed credentials in active channel tfvars"
  fi
}

assert_active_root_lockfiles_exist() {
  if [[ -f "${INFRA_DIR}/bootstrap/state-backend/.terraform.lock.hcl" \
    && -f "${INFRA_DIR}/roots/channels/dev/.terraform.lock.hcl" ]]; then
    pass "active root lockfiles exist"
  else
    fail "active root lockfiles exist"
  fi
}

# ---------------------------------------------------------------------------
section "Toolchain"
# ---------------------------------------------------------------------------

assert_tofu_version_111

# ---------------------------------------------------------------------------
section "File existence"
# ---------------------------------------------------------------------------

FILES=(
  "bootstrap/state-backend/main.tf"
  "modules/platform-network/main.tf"
  "modules/platform-cluster/main.tf"
  "bootstrap/state-backend/.terraform.lock.hcl"
  "schemas/platform-channel.schema.json"
  "schemas/platform-channel-resolved.schema.json"
  "channels/dev.yaml"
  "templates/platform-channel/main.tf"
  "templates/platform-channel/variables.tf"
  "templates/platform-channel/outputs.tf"
  "templates/platform-channel/versions.tf"
  "roots/channels/dev/main.tf"
  "roots/channels/dev/backend.tfbackend"
  "roots/channels/dev/channel.auto.tfvars.json"
  "roots/channels/dev/.terraform.lock.hcl"
  "modules/platform-network/versions.tf"
  "modules/platform-cluster/versions.tf"
  "scripts/resolve_platform_channel.py"
  "scripts/validate_platform_channels.py"
  "scripts/generate_channel_backend.py"
  "scripts/generate_channel_tfvars.py"
)

for file in "${FILES[@]}"; do
  assert_file_exists "$file"
done

assert_environments_dir_gone
assert_active_root_lockfiles_exist

# ---------------------------------------------------------------------------
section "Formatting checks"
# ---------------------------------------------------------------------------

assert_recursive_fmt_check
assert_bootstrap_tofu_validate
assert_dev_tofu_fmt_check

# ---------------------------------------------------------------------------
section "Structural validation"
# ---------------------------------------------------------------------------

assert_tofu_root_validates "roots/channels/dev" true

# ---------------------------------------------------------------------------
section "Content assertions: bootstrap/state-backend/main.tf"
# ---------------------------------------------------------------------------

BS="bootstrap/state-backend/main.tf"

assert_grep 'resource\s+"vultr_object_storage"' "$BS" \
  "declares vultr_object_storage resource"

assert_bootstrap_no_bucket_resource

assert_grep 'version\s*=\s*"~>\s*2\.30"' "$BS" \
  "provider version constraint ~> 2.30"

assert_grep 'required_version\s*=\s*">= 1\.8\.0"' "$BS" \
  "OpenTofu version constraint >= 1.8.0"

# ---------------------------------------------------------------------------
section "Content assertions: modules"
# ---------------------------------------------------------------------------

NET="modules/platform-network/main.tf"
CL="modules/platform-cluster/main.tf"

assert_grep 'resource\s+"vultr_vpc"' "$NET" \
  "declares vultr_vpc resource"

assert_grep 'resource\s+"vultr_kubernetes"' "$CL" \
  "declares vultr_kubernetes resource"

KUBE_CONFIG_FILE="${INFRA_DIR}/${CL}"
if grep -A2 'output\s*"kube_config"' "$KUBE_CONFIG_FILE" | grep -q 'sensitive\s*=\s*true'; then
  pass "kube_config output marked sensitive"
else
  fail "kube_config output marked sensitive"
fi

MODULES=(
  "modules/platform-network"
  "modules/platform-cluster"
)

for mod in "${MODULES[@]}"; do
  mod_file="${INFRA_DIR}/${mod}/main.tf"
  mod_versions="${mod}/versions.tf"
  mod_short="${mod}"

  assert_grep 'source\s*=\s*"vultr/vultr"' "$mod_versions" \
    "${mod_short}: declares vultr/vultr provider source"

  assert_no_grep '^backend\s+' "$mod_versions" \
    "${mod_short}: no backend block"

  assert_no_grep '^provider\s+' "${mod}/main.tf" \
    "${mod_short}: no provider block"

  if grep -n '"dev"\|"staging"\|"production"' "$mod_file" | grep -vE '^\s*#' >/dev/null; then
    fail "${mod_short}: no hardcoded environment names"
  else
    pass "${mod_short}: no hardcoded environment names"
  fi
done

# ---------------------------------------------------------------------------
section "Content assertions: platform template and dev root"
# ---------------------------------------------------------------------------

assert_rg_match 'module "network"|module "cluster"' "templates/platform-channel" \
  "template calls network and cluster modules"

assert_rg_no_match 'backend "s3"' "templates/platform-channel" \
  "template has no backend block"

assert_rg_match 'backend "s3"' "roots/channels/dev/main.tf" \
  "dev root has backend block"

assert_grep '../../../templates/platform-channel' "roots/channels/dev/main.tf" \
  "dev root references platform-channel template"

assert_grep 'version\s*=\s*"~>\s*2\.30"' "roots/channels/dev/main.tf" \
  "dev root provider version constraint ~> 2.30"

assert_grep 'required_version\s*=\s*">= 1\.8\.0"' "roots/channels/dev/main.tf" \
  "dev root OpenTofu version constraint >= 1.8.0"

assert_template_variables_documented

# ---------------------------------------------------------------------------
section "Generated artifact drift checks"
# ---------------------------------------------------------------------------

mkdir -p "${REPO_ROOT}/.tmp"
assert_backend_drift_check
assert_tfvars_drift_check
assert_generated_artifacts_covered

# ---------------------------------------------------------------------------
section "Security assertions"
# ---------------------------------------------------------------------------

assert_no_committed_credentials_in_tf
assert_no_committed_credentials_in_tfbackend
assert_no_committed_credentials_in_yaml
assert_no_committed_credentials_in_active_tfvars

CRED_PATTERNS='(api_key|api_token|secret_key|password|credential)\s*=\s*"[^"$]'

SECURITY_OK=true
while IFS= read -r -d '' tf_file; do
  rel="${tf_file#"${INFRA_DIR}/"}"
  if grep -iE "$CRED_PATTERNS" "$tf_file" | grep -vE '^\s*#' >/dev/null; then
    fail "no hardcoded credentials in ${rel}"
    SECURITY_OK=false
  fi
done < <(find "${INFRA_DIR}" -name '*.tf' -print0)

if [[ "$SECURITY_OK" == true ]]; then
  pass "no hardcoded credentials in any .tf file"
fi

S3_ACCESS_FILE="${INFRA_DIR}/bootstrap/state-backend/main.tf"
if grep -A2 'output\s*"s3_access_key"' "$S3_ACCESS_FILE" | grep -q 'sensitive\s*=\s*true'; then
  pass "s3_access_key output marked sensitive"
else
  fail "s3_access_key output marked sensitive"
fi

if grep -A2 'output\s*"s3_secret_key"' "$S3_ACCESS_FILE" | grep -q 'sensitive\s*=\s*true'; then
  pass "s3_secret_key output marked sensitive"
else
  fail "s3_secret_key output marked sensitive"
fi

assert_bootstrap_outputs_sensitive

BACKEND_FILE="${INFRA_DIR}/roots/channels/dev/backend.tfbackend"
if grep -iE '(access_key|secret_key)\s*=\s*"[^"]*[A-Za-z0-9]{10,}' "$BACKEND_FILE" >/dev/null; then
  fail "dev backend.tfbackend contains no actual credentials"
else
  pass "dev backend.tfbackend contains no actual credentials"
fi

assert_dev_backend_key
assert_no_credentials_in_dev_backend
assert_no_endpoint_in_dev_backend
assert_no_endpoint_placeholder
assert_readme_documents_locking_posture
assert_readme_documents_retirement
assert_readme_documents_optional_provider_plan
assert_readme_apply_is_out_of_scope

# ---------------------------------------------------------------------------
section "Authority alignment assertions"
# ---------------------------------------------------------------------------

assert_no_active_retired_provider_references
assert_decisions_d7_present

# ---------------------------------------------------------------------------
section "Channel registry assertions"
# ---------------------------------------------------------------------------

if python3 "${INFRA_DIR}/scripts/validate_platform_channels.py" >/dev/null; then
  pass "platform channels validate"
else
  fail "platform channels validate"
fi

DEV_RESOLVED="${REPO_ROOT}/.tmp/dev.resolved.json"
if python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" \
  --channel dev \
  --out "$DEV_RESOLVED" \
  && python3 -m json.tool "$DEV_RESOLVED" >/dev/null; then
  pass "dev channel resolves to JSON"
else
  fail "dev channel resolves to JSON"
fi

assert_json_value "$DEV_RESOLVED" "platform.region" "ewr" \
  "dev channel region is ewr"
assert_json_value "$DEV_RESOLVED" "platform.network.v4_subnet" "10.40.0.0" \
  "dev channel VPC subnet is preserved"
assert_json_value "$DEV_RESOLVED" "cluster.ha_controlplanes" "True" \
  "dev channel HA control planes are preserved"
assert_json_value "$DEV_RESOLVED" "cluster.enable_firewall" "True" \
  "dev channel firewall setting is preserved"

E2E_RESOLVED="${REPO_ROOT}/.tmp/e2e-from-dev.resolved.json"
if python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" \
  --channel e2e-from-dev \
  --out "$E2E_RESOLVED"; then
  assert_json_value "$E2E_RESOLVED" "platform.region" "ewr" \
    "e2e-from-dev inherits platform.region"
  assert_json_value "$E2E_RESOLVED" "cluster.label" "humility-e2e-from-dev-platform" \
    "e2e-from-dev overrides cluster.label"
else
  fail "e2e-from-dev resolves"
  fail "e2e-from-dev inherits platform.region"
  fail "e2e-from-dev overrides cluster.label"
fi

E2E_PR_RESOLVED="${REPO_ROOT}/.tmp/e2e-pr-1234.resolved.json"
if python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" \
  --channel e2e-pr-1234 \
  --out "$E2E_PR_RESOLVED"; then
  assert_json_value "$E2E_PR_RESOLVED" "platform.region" "ewr" \
    "e2e-pr-1234 inherits platform.region from dev"
  assert_json_value "$E2E_PR_RESOLVED" "cluster.label" "humility-e2e-from-dev-platform" \
    "e2e-pr-1234 inherits cluster.label from e2e-from-dev"
  assert_json_value "$E2E_PR_RESOLVED" "tenant" "pr-1234" \
    "e2e-pr-1234 applies tenant override"
else
  fail "e2e-pr-1234 resolves"
  fail "e2e-pr-1234 inherits platform.region from dev"
  fail "e2e-pr-1234 inherits cluster.label from e2e-from-dev"
  fail "e2e-pr-1234 applies tenant override"
fi

MISSING_PARENT_ERR="${REPO_ROOT}/.tmp/missing-parent.err"
if ! python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" \
  --channel missing-parent \
  --out "${REPO_ROOT}/.tmp/missing-parent.resolved.json" \
  2>"$MISSING_PARENT_ERR" \
  && grep -q '"code": "missing_parent"' "$MISSING_PARENT_ERR"; then
  pass "missing-parent fails with missing_parent"
else
  fail "missing-parent fails with missing_parent"
fi

CIRCULAR_PARENT_ERR="${REPO_ROOT}/.tmp/circular-parent.err"
if ! python3 "${INFRA_DIR}/scripts/resolve_platform_channel.py" \
  --channel circular-a \
  --out "${REPO_ROOT}/.tmp/circular-a.resolved.json" \
  2>"$CIRCULAR_PARENT_ERR" \
  && grep -q '"code": "circular_parent"' "$CIRCULAR_PARENT_ERR"; then
  pass "circular-a fails with circular_parent"
else
  fail "circular-a fails with circular_parent"
fi

SPAWN_DIR="${REPO_ROOT}/.tmp/platform-channels/dev-pr-123"
rm -rf "$SPAWN_DIR"
if python3 "${INFRA_DIR}/scripts/spawn_platform_channel.py" \
  --parent dev \
  --suffix pr-123 \
  --out "$SPAWN_DIR" \
  && [[ -f "${SPAWN_DIR}/channel.yaml" ]]; then
  pass "spawn succeeds on dev under .tmp"
else
  fail "spawn succeeds on dev under .tmp"
fi

SPAWN_DISABLED_ERR="${REPO_ROOT}/.tmp/spawn-disabled.err"
if ! python3 "${INFRA_DIR}/scripts/spawn_platform_channel.py" \
  --parent ephemeral-disabled \
  --suffix pr-123 \
  --out "${REPO_ROOT}/.tmp/platform-channels/ephemeral-disabled-pr-123" \
  2>"$SPAWN_DISABLED_ERR" \
  && grep -q '"code": "ephemeral_children_disabled"' "$SPAWN_DISABLED_ERR"; then
  pass "spawn blocked on disabled parent"
else
  fail "spawn blocked on disabled parent"
fi

if find "${INFRA_DIR}/channels" \
  \( -name customer.yaml -o -name internal.yaml -o -name e2e.yaml \) \
  -print -quit | grep -q .; then
  fail "forbidden channel files absent"
else
  pass "forbidden channel files absent"
fi

# ---------------------------------------------------------------------------
section "Summary"
# ---------------------------------------------------------------------------

TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo ""
echo "Results: ${PASS_COUNT}/${TOTAL} passed, ${FAIL_COUNT} failed"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "STATUS: FAILED"
  exit 1
else
  echo "STATUS: ALL PASSED"
  exit 0
fi
