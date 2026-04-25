#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GITOPS_DIR="${REPO_ROOT}/gitops"
INSTALL_SCRIPT="${GITOPS_DIR}/scripts/install-tools.sh"

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

assert_no_legacy_k8s_dir() {
  if [[ ! -d "${REPO_ROOT}/k8s" ]]; then
    pass "legacy k8s directory removed"
  else
    fail "legacy k8s directory removed"
  fi
}

assert_install_script_executable() {
  if [[ -x "$INSTALL_SCRIPT" ]]; then
    pass "install-tools.sh is executable"
  else
    fail "install-tools.sh is executable"
  fi
}

assert_install_script_pins_versions() {
  local ok=true

  grep -q 'readonly FLUX_VERSION="2.8.0"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'readonly KIND_VERSION="0.31.0"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'readonly SOPS_VERSION="3.10.0"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'readonly AGE_VERSION="1.3.0"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'readonly KUBECTL_MIN="1.31.0"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'readonly KUSTOMIZE_MIN="5.7.1"' "$INSTALL_SCRIPT" || ok=false

  if [[ "$ok" == true ]]; then
    pass "install-tools.sh pins required versions"
  else
    fail "install-tools.sh pins required versions"
  fi
}

assert_install_script_uses_official_sources() {
  local ok=true

  grep -q 'github.com/fluxcd/flux2/releases/download' "$INSTALL_SCRIPT" || ok=false
  grep -q 'github.com/kubernetes-sigs/kind/releases/download' "$INSTALL_SCRIPT" || ok=false
  grep -q 'github.com/getsops/sops/releases/download' "$INSTALL_SCRIPT" || ok=false
  grep -q 'github.com/FiloSottile/age/releases/download' "$INSTALL_SCRIPT" || ok=false

  if [[ "$ok" == true ]]; then
    pass "install-tools.sh uses official upstream release URLs"
  else
    fail "install-tools.sh uses official upstream release URLs"
  fi
}

assert_install_script_pins_sha256() {
  local ok=true

  grep -Eq 'readonly FLUX_SHA256="[0-9a-f]{64}"' "$INSTALL_SCRIPT" || ok=false
  grep -Eq 'readonly KIND_SHA256="[0-9a-f]{64}"' "$INSTALL_SCRIPT" || ok=false
  grep -Eq 'readonly SOPS_SHA256="[0-9a-f]{64}"' "$INSTALL_SCRIPT" || ok=false
  grep -Eq 'readonly AGE_SHA256="[0-9a-f]{64}"' "$INSTALL_SCRIPT" || ok=false
  grep -q 'sha256sum' "$INSTALL_SCRIPT" || ok=false

  if [[ "$ok" == true ]]; then
    pass "install-tools.sh verifies pinned SHA256 checksums"
  else
    fail "install-tools.sh verifies pinned SHA256 checksums"
  fi
}

assert_install_tools_check_reports_status() {
  local output_file error_file status
  output_file="${REPO_ROOT}/.tmp/gitops-install-tools-check.out"
  error_file="${REPO_ROOT}/.tmp/gitops-install-tools-check.err"
  mkdir -p "${REPO_ROOT}/.tmp"

  set +e
  bash "$INSTALL_SCRIPT" --check --no-color >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 ]]; then
    pass "install-tools.sh --check passes with installed toolchain"
    return
  fi

  if grep -q 'STATUS: FAILED' "$output_file" \
    && grep -q 'Missing or below-minimum tools:' "$output_file" \
    && grep -q 'flux' "$output_file" \
    && grep -q 'kind' "$output_file" \
    && grep -q 'sops' "$output_file" \
    && grep -q 'age-keygen' "$output_file" \
    && grep -q 'kubectl' "$output_file"; then
    pass "install-tools.sh --check clearly reports missing or below-minimum tools"
  else
    fail "install-tools.sh --check clearly reports missing or below-minimum tools"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
  fi
}

section "GitOps Toolchain"
assert_install_script_executable
assert_install_script_pins_versions
assert_install_script_uses_official_sources
assert_install_script_pins_sha256
assert_install_tools_check_reports_status

section "Legacy Layout"
assert_no_legacy_k8s_dir

section "Summary"
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
