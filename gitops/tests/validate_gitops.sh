#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GITOPS_DIR="${REPO_ROOT}/gitops"
INSTALL_SCRIPT="${GITOPS_DIR}/scripts/install-tools.sh"

PASS_COUNT=0
FAIL_COUNT=0
LAYOUT_ONLY=false
FLUX_RENDER_ONLY=false

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

usage() {
  cat <<'USAGE'
Usage: validate_gitops.sh [--layout-only|--flux-render-only]

Validates the INIT-009 GitOps substrate.

Options:
  --layout-only        Run only gitops/ layout and Kustomize assertions.
  --flux-render-only   Run only Flux self-management render assertions.
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --layout-only)
      LAYOUT_ONLY=true
      ;;
    --flux-render-only)
      FLUX_RENDER_ONLY=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ "$LAYOUT_ONLY" == true && "$FLUX_RENDER_ONLY" == true ]]; then
  echo "ERROR: --layout-only and --flux-render-only are mutually exclusive" >&2
  usage >&2
  exit 2
fi

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

assert_dir_exists() {
  local path="$1"
  if [[ -d "${REPO_ROOT}/${path}" ]]; then
    pass "directory exists: ${path}"
  else
    fail "directory exists: ${path}"
  fi
}

assert_file_exists() {
  local path="$1"
  if [[ -f "${REPO_ROOT}/${path}" ]]; then
    pass "file exists: ${path}"
  else
    fail "file exists: ${path}"
  fi
}

assert_gitops_dirs_exist() {
  local dir
  local dirs=(
    gitops
    gitops/bases
    gitops/bases/flux-system
    gitops/bases/crossplane
    gitops/bases/cert-manager
    gitops/bases/external-dns
    gitops/bases/cluster-security
    gitops/channels
    gitops/channels/dev
    gitops/secrets
    gitops/secrets/dev
  )

  for dir in "${dirs[@]}"; do
    assert_dir_exists "$dir"
  done
}

assert_each_base_has_readme_and_kustomization() {
  local base_dir rel_path
  while IFS= read -r base_dir; do
    rel_path="${base_dir#${REPO_ROOT}/}"
    assert_file_exists "${rel_path}/README.md"
    assert_file_exists "${rel_path}/kustomization.yaml"
  done < <(find "${GITOPS_DIR}/bases" -mindepth 1 -maxdepth 1 -type d | sort)
}

assert_each_channel_has_readme_and_kustomization() {
  local channel_dir rel_path
  while IFS= read -r channel_dir; do
    rel_path="${channel_dir#${REPO_ROOT}/}"
    assert_file_exists "${rel_path}/README.md"
    assert_file_exists "${rel_path}/kustomization.yaml"
  done < <(find "${GITOPS_DIR}/channels" -mindepth 1 -maxdepth 1 -type d | sort)
}

assert_kustomization_resources_empty() {
  local file="$1"
  local label="$2"

  if command -v yq >/dev/null 2>&1; then
    if yq -e '.resources == []' "$file" >/dev/null 2>&1; then
      pass "$label"
    else
      fail "$label"
    fi
    return
  fi

  if grep -Eq '^resources:[[:space:]]*\[\][[:space:]]*$' "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

assert_placeholder_bases_empty() {
  local base
  local bases=(crossplane cert-manager external-dns cluster-security)

  for base in "${bases[@]}"; do
    assert_kustomization_resources_empty \
      "${GITOPS_DIR}/bases/${base}/kustomization.yaml" \
      "placeholder base is empty: ${base}"
  done
}

assert_dev_channel_composes_all_bases() {
  local file="${GITOPS_DIR}/channels/dev/kustomization.yaml"
  local ok=true
  local resource
  local resources=(
    ../../bases/flux-system
    ../../bases/crossplane
    ../../bases/cert-manager
    ../../bases/external-dns
    ../../bases/cluster-security
    ../../secrets/dev
  )

  for resource in "${resources[@]}"; do
    grep -Eq "^[[:space:]]*-[[:space:]]+${resource//\//\\/}[[:space:]]*$" "$file" || ok=false
  done

  if [[ "$ok" == true ]]; then
    pass "dev channel composes all bases and secrets/dev"
  else
    fail "dev channel composes all bases and secrets/dev"
  fi
}

assert_kustomize_build_dev_channel() {
  local output_file error_file status
  output_file="${REPO_ROOT}/.tmp/gitops-kustomize-dev.out"
  error_file="${REPO_ROOT}/.tmp/gitops-kustomize-dev.err"
  mkdir -p "${REPO_ROOT}/.tmp"

  set +e
  kubectl kustomize "${GITOPS_DIR}/channels/dev" >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 && -s "$output_file" ]]; then
    pass "kubectl kustomize gitops/channels/dev succeeds"
  else
    fail "kubectl kustomize gitops/channels/dev succeeds"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
  fi
}

assert_flux_components_exist() {
  local file="${GITOPS_DIR}/bases/flux-system/gotk-components.yaml"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -q '^# Flux Version: v2\.8\.0$' "$file" || ok=false
  grep -q '^kind: Namespace$' "$file" || ok=false
  grep -q '^  name: flux-system$' "$file" || ok=false
  grep -q 'source-controller' "$file" || ok=false
  grep -q 'kustomize-controller' "$file" || ok=false
  grep -q 'helm-controller' "$file" || ok=false
  grep -q 'notification-controller' "$file" || ok=false
  grep -q 'image-reflector-controller' "$file" || ok=false
  grep -q 'image-automation-controller' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "Flux v2.8.0 components manifest exists"
  else
    fail "Flux v2.8.0 components manifest exists"
  fi
}

assert_flux_base_kustomize_build_succeeds() {
  local output_file error_file status
  output_file="${REPO_ROOT}/.tmp/gitops-kustomize-flux-system.out"
  error_file="${REPO_ROOT}/.tmp/gitops-kustomize-flux-system.err"
  mkdir -p "${REPO_ROOT}/.tmp"

  set +e
  kubectl kustomize "${GITOPS_DIR}/bases/flux-system" >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 && -s "$output_file" ]]; then
    pass "kubectl kustomize gitops/bases/flux-system succeeds"
  else
    fail "kubectl kustomize gitops/bases/flux-system succeeds"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
  fi
}

assert_gitrepository_interval_1m() {
  local file="${GITOPS_DIR}/bases/flux-system/source-gitrepository.yaml"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -q '^kind: GitRepository$' "$file" || ok=false
  grep -q '^  name: server-manager$' "$file" || ok=false
  grep -q '^  namespace: flux-system$' "$file" || ok=false
  grep -q '^  interval: 1m$' "$file" || ok=false
  grep -q '^    branch: main$' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "server-manager GitRepository interval is 1m"
  else
    fail "server-manager GitRepository interval is 1m"
  fi
}

assert_root_kustomization_interval_5m() {
  local file="${GITOPS_DIR}/bases/flux-system/root-kustomization.yaml"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -q '^kind: Kustomization$' "$file" || ok=false
  grep -q '^  name: server-manager-dev$' "$file" || ok=false
  grep -q '^  namespace: flux-system$' "$file" || ok=false
  grep -q '^  interval: 5m$' "$file" || ok=false
  grep -q '^  prune: true$' "$file" || ok=false
  grep -q '^  wait: true$' "$file" || ok=false
  grep -q '^  path: ./gitops/channels/dev$' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "server-manager-dev root Kustomization points at dev"
  else
    fail "server-manager-dev root Kustomization points at dev"
  fi
}

assert_dev_channel_kustomize_build_succeeds() {
  local output_file error_file status
  output_file="${REPO_ROOT}/.tmp/gitops-flux-render-dev.out"
  error_file="${REPO_ROOT}/.tmp/gitops-flux-render-dev.err"
  mkdir -p "${REPO_ROOT}/.tmp"

  set +e
  kubectl kustomize "${GITOPS_DIR}/channels/dev" >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 && -s "$output_file" ]]; then
    pass "kubectl kustomize gitops/channels/dev renders non-empty output"
  else
    fail "kubectl kustomize gitops/channels/dev renders non-empty output"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
  fi
}

assert_no_forbidden_paths_in_dev_render() {
  local output_file="${REPO_ROOT}/.tmp/gitops-flux-render-dev.out"
  local ok=true
  local forbidden
  local forbidden_paths=(
    'k8s/'
    'gitops/bases/crossplane/'
    'gitops/bases/cert-manager/'
    'gitops/bases/external-dns/'
    'gitops/bases/cluster-security/'
  )

  if [[ ! -s "$output_file" ]]; then
    kubectl kustomize "${GITOPS_DIR}/channels/dev" >"$output_file"
  fi

  for forbidden in "${forbidden_paths[@]}"; do
    grep -q "$forbidden" "$output_file" && ok=false
  done

  if [[ "$ok" == true ]]; then
    pass "dev render does not reference legacy or populated placeholder paths"
  else
    fail "dev render does not reference legacy or populated placeholder paths"
  fi
}

assert_local_source_patch_present() {
  local file="${GITOPS_DIR}/channels/dev/patches/flux-source-local.yaml"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -q '^kind: GitRepository$' "$file" || ok=false
  grep -q '^  name: server-manager$' "$file" || ok=false
  grep -q '^  namespace: flux-system$' "$file" || ok=false
  grep -q 'gitea-local' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "local Flux source patch is present"
  else
    fail "local Flux source patch is present"
  fi
}

run_layout_checks() {
  section "GitOps Layout"
  assert_gitops_dirs_exist
  assert_each_base_has_readme_and_kustomization
  assert_each_channel_has_readme_and_kustomization
  assert_placeholder_bases_empty
  assert_dev_channel_composes_all_bases
  assert_kustomize_build_dev_channel
}

run_tool_checks() {
  section "GitOps Toolchain"
  assert_install_script_executable
  assert_install_script_pins_versions
  assert_install_script_uses_official_sources
  assert_install_script_pins_sha256
  assert_install_tools_check_reports_status

  section "Legacy Layout"
  assert_no_legacy_k8s_dir
}

run_flux_render_checks() {
  section "Flux Self-Management Render"
  assert_flux_components_exist
  assert_flux_base_kustomize_build_succeeds
  assert_gitrepository_interval_1m
  assert_root_kustomization_interval_5m
  assert_local_source_patch_present
  assert_dev_channel_kustomize_build_succeeds
  assert_no_forbidden_paths_in_dev_render
}

if [[ "$FLUX_RENDER_ONLY" == true ]]; then
  run_flux_render_checks
elif [[ "$LAYOUT_ONLY" == true ]]; then
  run_layout_checks
else
  run_layout_checks
  run_flux_render_checks
  run_tool_checks
fi

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
