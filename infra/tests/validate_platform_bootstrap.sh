#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0

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
  if [[ ! -f "${INFRA_DIR}/${file}" ]]; then
    fail "File missing: ${file}"
    return 1
  fi
  return 0
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

# ---------------------------------------------------------------------------
section "File existence"
# ---------------------------------------------------------------------------

FILES=(
  "bootstrap/state-backend/main.tf"
  "modules/platform-network/main.tf"
  "modules/platform-cluster/main.tf"
  "environments/dev/main.tf"
  "environments/dev/backend.tfbackend"
)

ALL_EXIST=true
for f in "${FILES[@]}"; do
  if assert_file_exists "$f"; then
    pass "exists: ${f}"
  else
    ALL_EXIST=false
  fi
done

if [[ "$ALL_EXIST" != true ]]; then
  echo ""
  echo "ABORT: required files missing — remaining checks would be meaningless."
  exit 1
fi

# ---------------------------------------------------------------------------
section "Formatting checks"
# ---------------------------------------------------------------------------

FMT_TOOL=""
if command -v tofu &>/dev/null; then
  FMT_TOOL="tofu"
elif command -v terraform &>/dev/null; then
  FMT_TOOL="terraform"
fi

if [[ -n "$FMT_TOOL" ]]; then
  if $FMT_TOOL fmt -check -recursive "${INFRA_DIR}/" &>/dev/null; then
    pass "fmt check (${FMT_TOOL} fmt -check -recursive)"
  else
    fail "fmt check (${FMT_TOOL} fmt -check -recursive)"
  fi
else
  echo "  INFO: tofu/terraform not found — falling back to heuristic indentation checks"

  FMT_HEURISTIC_OK=true
  for f in "${FILES[@]}"; do
    filepath="${INFRA_DIR}/${f}"
    [[ "$f" != *.tf ]] && continue

    if grep -Pn '^\t' "$filepath" &>/dev/null; then
      fail "heuristic fmt: tabs found in ${f} (HCL uses spaces)"
      FMT_HEURISTIC_OK=false
    fi

    if grep -Pn '^ {1,1}[^ ]' "$filepath" &>/dev/null; then
      fail "heuristic fmt: 1-space indentation in ${f} (expect 2)"
      FMT_HEURISTIC_OK=false
    fi

    if grep -Pn '^ {3}[^ ]' "$filepath" &>/dev/null; then
      fail "heuristic fmt: 3-space indentation in ${f} (expect 2)"
      FMT_HEURISTIC_OK=false
    fi
  done

  if [[ "$FMT_HEURISTIC_OK" == true ]]; then
    pass "heuristic fmt: indentation looks consistent across .tf files"
  fi
fi

# ---------------------------------------------------------------------------
section "Structural validation (tofu validate)"
# ---------------------------------------------------------------------------

VALIDATE_TOOL=""
if command -v tofu &>/dev/null; then
  VALIDATE_TOOL="tofu"
elif command -v terraform &>/dev/null; then
  VALIDATE_TOOL="terraform"
fi

VALIDATE_ROOTS=(
  "bootstrap/state-backend"
  "environments/dev"
)

if [[ -n "$VALIDATE_TOOL" ]]; then
  for root in "${VALIDATE_ROOTS[@]}"; do
    root_dir="${INFRA_DIR}/${root}"
    pushd "$root_dir" >/dev/null

    if $VALIDATE_TOOL init -backend=false &>/dev/null; then
      if $VALIDATE_TOOL validate &>/dev/null; then
        pass "${VALIDATE_TOOL} validate: ${root}"
      else
        fail "${VALIDATE_TOOL} validate: ${root}"
      fi
    else
      fail "${VALIDATE_TOOL} init -backend=false: ${root}"
    fi

    rm -rf .terraform .terraform.lock.hcl 2>/dev/null || true
    popd >/dev/null
  done
else
  echo "  INFO: tofu/terraform not found — falling back to structural grep checks"

  for root in "${VALIDATE_ROOTS[@]}"; do
    tf_file="${INFRA_DIR}/${root}/main.tf"

    if grep -qE '^terraform\s*\{' "$tf_file"; then
      pass "structural: terraform block found in ${root}/main.tf"
    else
      fail "structural: terraform block missing in ${root}/main.tf"
    fi

    if grep -qE 'required_providers' "$tf_file"; then
      pass "structural: required_providers found in ${root}/main.tf"
    else
      fail "structural: required_providers missing in ${root}/main.tf"
    fi

    if grep -qE '^provider\s+"vultr"' "$tf_file"; then
      pass "structural: provider vultr declared in ${root}/main.tf"
    else
      fail "structural: provider vultr missing in ${root}/main.tf"
    fi
  done
fi

# ---------------------------------------------------------------------------
section "Content assertions: bootstrap/state-backend/main.tf"
# ---------------------------------------------------------------------------

BS="bootstrap/state-backend/main.tf"

assert_grep 'resource\s+"vultr_object_storage"' "$BS" \
  "declares vultr_object_storage resource"

assert_grep 'resource\s+"vultr_object_storage_bucket"' "$BS" \
  "declares vultr_object_storage_bucket resource"

assert_grep 'enable_versioning\s*=\s*true' "$BS" \
  "enable_versioning = true"

assert_grep 'version\s*=\s*"~>\s*2\.30"' "$BS" \
  "provider version constraint ~> 2.30"

assert_grep 'required_version\s*=\s*">= 1\.8\.0"' "$BS" \
  "OpenTofu version constraint >= 1.8.0"

# ---------------------------------------------------------------------------
section "Content assertions: modules/platform-network/main.tf"
# ---------------------------------------------------------------------------

NET="modules/platform-network/main.tf"

assert_grep 'resource\s+"vultr_vpc"' "$NET" \
  "declares vultr_vpc resource"

# ---------------------------------------------------------------------------
section "Content assertions: modules/platform-cluster/main.tf"
# ---------------------------------------------------------------------------

CL="modules/platform-cluster/main.tf"

assert_grep 'resource\s+"vultr_kubernetes"' "$CL" \
  "declares vultr_kubernetes resource"

KUBE_CONFIG_FILE="${INFRA_DIR}/${CL}"
if grep -A2 'output\s*"kube_config"' "$KUBE_CONFIG_FILE" | grep -q 'sensitive\s*=\s*true'; then
  pass "kube_config output marked sensitive"
else
  fail "kube_config output marked sensitive"
fi

# ---------------------------------------------------------------------------
section "Content assertions: environments/dev/main.tf"
# ---------------------------------------------------------------------------

DEV="environments/dev/main.tf"

assert_grep 'backend\s+"s3"\s*\{\}' "$DEV" \
  "uses backend \"s3\" {}"

assert_grep '../../modules/platform-network' "$DEV" \
  "references ../../modules/platform-network"

assert_grep '../../modules/platform-cluster' "$DEV" \
  "references ../../modules/platform-cluster"

assert_grep 'version\s*=\s*"~>\s*2\.30"' "$DEV" \
  "provider version constraint ~> 2.30"

assert_grep 'required_version\s*=\s*">= 1\.8\.0"' "$DEV" \
  "OpenTofu version constraint >= 1.8.0"

# ---------------------------------------------------------------------------
section "Content assertions: environments/dev/backend.tfbackend"
# ---------------------------------------------------------------------------

BE="environments/dev/backend.tfbackend"

assert_grep 'bucket\s*=\s*"humility-tfstate"' "$BE" \
  "bucket = humility-tfstate"

# ---------------------------------------------------------------------------
section "Module isolation assertions"
# ---------------------------------------------------------------------------

MODULES=(
  "modules/platform-network/main.tf"
  "modules/platform-cluster/main.tf"
)

for mod in "${MODULES[@]}"; do
  mod_file="${INFRA_DIR}/${mod}"
  mod_short="${mod%/main.tf}"

  assert_no_grep '^terraform\s*\{' "$mod" \
    "${mod_short}: no terraform {} block"

  assert_no_grep '^provider\s+' "$mod" \
    "${mod_short}: no provider block"

  if grep -n '"dev"\|"staging"\|"production"' "$mod_file" | grep -vE '^\s*#' &>/dev/null; then
    fail "${mod_short}: no hardcoded environment names"
  else
    pass "${mod_short}: no hardcoded environment names"
  fi
done

# ---------------------------------------------------------------------------
section "Security assertions"
# ---------------------------------------------------------------------------

CRED_PATTERNS='(api_key|api_token|secret_key|password|credential)\s*=\s*"[^"$]'

SECURITY_OK=true
while IFS= read -r -d '' tf_file; do
  rel="${tf_file#"${INFRA_DIR}/"}"
  if grep -iE "$CRED_PATTERNS" "$tf_file" | grep -vE '^\s*#' &>/dev/null; then
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

BACKEND_FILE="${INFRA_DIR}/environments/dev/backend.tfbackend"
if grep -iE '(access_key|secret_key)\s*=\s*"[^"]*[A-Za-z0-9]{10,}' "$BACKEND_FILE" &>/dev/null; then
  fail "backend.tfbackend contains no actual credentials"
else
  pass "backend.tfbackend contains no actual credentials"
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
