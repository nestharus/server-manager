#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GITOPS_DIR="${REPO_ROOT}/gitops"
INSTALL_SCRIPT="${GITOPS_DIR}/scripts/install-tools.sh"
BOOTSTRAP_SCRIPT="${GITOPS_DIR}/scripts/bootstrap-flux.sh"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
LAYOUT_ONLY=false
FLUX_RENDER_ONLY=false
SOPS_ONLY=false
CLUSTER_ONLY=false

pass() {
  echo "  PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "  SKIPPED: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

placeholder() {
  echo "  PLACEHOLDER: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

section() {
  echo ""
  echo "=== $1 ==="
}

usage() {
  cat <<'USAGE'
Usage: validate_gitops.sh [--layout-only|--flux-render-only|--sops-only|--cluster]

Validates the INIT-009 GitOps substrate.

Options:
  --layout-only        Run only gitops/ layout and Kustomize assertions.
  --flux-render-only   Run only Flux self-management render assertions.
  --sops-only          Run only SOPS+age per-channel secret assertions.
  --cluster            Run local kind + Flux bootstrap if required tools exist.
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
    --sops-only)
      SOPS_ONLY=true
      ;;
    --cluster)
      CLUSTER_ONLY=true
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

MODE_COUNT=0
for selected_mode in "$LAYOUT_ONLY" "$FLUX_RENDER_ONLY" "$SOPS_ONLY" "$CLUSTER_ONLY"; do
  if [[ "$selected_mode" == true ]]; then
    MODE_COUNT=$((MODE_COUNT + 1))
  fi
done

if [[ "$MODE_COUNT" -gt 1 ]]; then
  echo "ERROR: --layout-only, --flux-render-only, --sops-only, and --cluster are mutually exclusive" >&2
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

assert_bootstrap_script_executable() {
  if [[ -x "$BOOTSTRAP_SCRIPT" ]]; then
    pass "bootstrap-flux.sh is executable"
  else
    fail "bootstrap-flux.sh is executable"
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
  grep -q 'git://git-local.git-system.svc.cluster.local/server-manager.git' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "local Flux source patch is present"
  else
    fail "local Flux source patch is present"
  fi
}

assert_local_source_patch_concrete() {
  local file="${GITOPS_DIR}/channels/dev/patches/flux-source-local.yaml"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -Eq '^[[:space:]]*url:[[:space:]]+(git|https?|ssh)://' "$file" || ok=false
  grep -qi 'placeholder\|replace_with\|todo' "$file" && ok=false

  if [[ "$ok" == true ]]; then
    pass "local Flux source patch has a concrete URL"
  else
    fail "local Flux source patch has a concrete URL"
  fi
}

dev_sops_file() {
  printf '%s\n' "${GITOPS_DIR}/secrets/dev/.sops.yaml"
}

dev_bootstrap_secret_file() {
  printf '%s\n' "${GITOPS_DIR}/secrets/dev/bootstrap-creds.enc.yaml"
}

has_real_dev_age_recipient() {
  grep -Eq 'age1[a-z0-9]{58}' "$(dev_sops_file)"
}

has_placeholder_dev_age_recipient() {
  grep -q '<REPLACE_WITH_REAL_RECIPIENT_BEFORE_USE>' "$(dev_sops_file)"
}

assert_dev_sops_yaml_exists() {
  if [[ -f "$(dev_sops_file)" ]]; then
    pass "dev .sops.yaml exists"
  else
    fail "dev .sops.yaml exists"
  fi
}

assert_dev_sops_yaml_has_creation_rule() {
  local file
  file="$(dev_sops_file)"
  local ok=true

  [[ -f "$file" ]] || ok=false
  grep -q '^creation_rules:' "$file" || ok=false
  grep -q 'path_regex: gitops/secrets/dev/.*\\.enc\\.yaml' "$file" || ok=false
  grep -q 'encrypted_regex: \^(data|stringData)\$' "$file" || ok=false
  grep -q '^    age:' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "dev .sops.yaml has a creation_rules block"
  else
    fail "dev .sops.yaml has a creation_rules block"
  fi
}

assert_dev_sops_yaml_has_recipient() {
  if [[ ! -f "$(dev_sops_file)" ]]; then
    fail "dev .sops.yaml lists an age recipient"
    return
  fi

  if has_real_dev_age_recipient; then
    pass "dev .sops.yaml lists a real age recipient"
  elif has_placeholder_dev_age_recipient; then
    placeholder "dev .sops.yaml has REPLACE-before-use age recipient because age-keygen is unavailable"
  else
    fail "dev .sops.yaml lists an age recipient"
  fi
}

assert_dev_bootstrap_secret_exists() {
  if [[ -f "$(dev_bootstrap_secret_file)" ]]; then
    pass "bootstrap-creds.enc.yaml exists"
  else
    fail "bootstrap-creds.enc.yaml exists"
  fi
}

assert_bootstrap_flux_script_exists() {
  local file="$BOOTSTRAP_SCRIPT"
  local ok=true

  [[ -x "$file" ]] || ok=false
  grep -q 'age-keygen' "$file" || ok=false
  grep -q 'DEV_AGE_KEY' "$file" || ok=false

  if [[ "$ok" == true ]]; then
    pass "bootstrap-flux.sh includes executable dev age-key generation"
  else
    fail "bootstrap-flux.sh includes executable dev age-key generation"
  fi
}

assert_dev_enc_files_have_sops_metadata() {
  local enc_file rel_path found=false

  while IFS= read -r enc_file; do
    found=true
    rel_path="${enc_file#${REPO_ROOT}/}"

    if grep -q '^sops:' "$enc_file"; then
      pass "${rel_path} has SOPS metadata"
    elif grep -q 'PLACEHOLDER' "$enc_file"; then
      placeholder "${rel_path} is a documented placeholder until sops/age are installed"
    else
      fail "${rel_path} has SOPS metadata"
    fi
  done < <(find "${GITOPS_DIR}/secrets/dev" -maxdepth 1 -name '*.enc.yaml' -type f | sort)

  if [[ "$found" == false ]]; then
    skip "no dev *.enc.yaml files found for SOPS metadata check"
  fi
}

assert_bootstrap_script_help_works() {
  local output_file error_file status
  output_file="${REPO_ROOT}/.tmp/gitops-bootstrap-help.out"
  error_file="${REPO_ROOT}/.tmp/gitops-bootstrap-help.err"
  mkdir -p "${REPO_ROOT}/.tmp"

  set +e
  bash "$BOOTSTRAP_SCRIPT" help >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 ]] \
    && grep -q 'age-key' "$output_file" \
    && grep -q 'cluster-up' "$output_file" \
    && grep -q 'bootstrap' "$output_file" \
    && grep -q 'teardown' "$output_file"; then
    pass "bootstrap-flux.sh help exits 0 and lists subcommands"
  else
    fail "bootstrap-flux.sh help exits 0 and lists subcommands"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
  fi
}

assert_bootstrap_script_required_functions() {
  local ok=true
  local function_name
  local functions=(
    ensure_age_installed
    ensure_dev_age_key
    ensure_kind_installed
    ensure_flux_installed
    create_kind_cluster
    flux_check_pre
    bootstrap_flux
    verify_reconciled
    teardown_kind_cluster
  )

  for function_name in "${functions[@]}"; do
    grep -Eq "^${function_name}\\(\\)[[:space:]]*\\{" "$BOOTSTRAP_SCRIPT" || ok=false
  done

  if [[ "$ok" == true ]]; then
    pass "bootstrap-flux.sh contains required functions"
  else
    fail "bootstrap-flux.sh contains required functions"
  fi
}

assert_kind_cluster_creation_path_documented() {
  if grep -q '^create_kind_cluster()' "$BOOTSTRAP_SCRIPT"; then
    pass "kind cluster creation path is documented in bootstrap-flux.sh"
  else
    fail "kind cluster creation path is documented in bootstrap-flux.sh"
  fi
}

assert_flux_check_pre_in_bootstrap() {
  if grep -q 'flux check --pre' "$BOOTSTRAP_SCRIPT"; then
    pass "bootstrap-flux.sh invokes flux check --pre"
  else
    fail "bootstrap-flux.sh invokes flux check --pre"
  fi
}

assert_bootstrap_script_idempotent() {
  if grep -q 'kind get clusters' "$BOOTSTRAP_SCRIPT" \
    && grep -q 'grep -qx "$cluster_name"' "$BOOTSTRAP_SCRIPT" \
    && grep -q "already exists" "$BOOTSTRAP_SCRIPT"; then
    pass "cluster-up idempotency check exists"
  else
    fail "cluster-up idempotency check exists"
  fi
}

assert_local_git_mechanism_documented() {
  if grep -q 'git daemon' "$BOOTSTRAP_SCRIPT" \
    && grep -q 'git://git-local.git-system.svc.cluster.local/server-manager.git' "$BOOTSTRAP_SCRIPT"; then
    pass "bootstrap-flux.sh documents the local Git mechanism"
  else
    fail "bootstrap-flux.sh documents the local Git mechanism"
  fi
}

run_cluster_bootstrap_if_tools_present() {
  local missing=()
  local tool

  for tool in kind flux kubectl age-keygen git tar; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    fi
  done

  if [[ "${#missing[@]}" -gt 0 ]]; then
    skip "cluster bootstrap skipped because required tools are missing: ${missing[*]}"
    return
  fi

  bash "$BOOTSTRAP_SCRIPT" bootstrap
  pass "bootstrap-flux.sh bootstrap completed against local kind"
}

assert_sops_decrypt_works_if_tools_present() {
  local sample output_file error_file status key_file
  sample="$(dev_bootstrap_secret_file)"
  output_file="${REPO_ROOT}/.tmp/gitops-sops-decrypt.out"
  error_file="${REPO_ROOT}/.tmp/gitops-sops-decrypt.err"
  key_file="${SOPS_AGE_KEY_FILE:-${HOME}/.config/sops/age/dev.txt}"
  mkdir -p "${REPO_ROOT}/.tmp"

  if ! command -v sops >/dev/null 2>&1; then
    skip "sops decrypt verification skipped because sops is not installed"
    return
  fi

  if ! command -v age >/dev/null 2>&1; then
    skip "sops decrypt verification skipped because age is not installed"
    return
  fi

  if [[ ! -f "$(dev_sops_file)" ]] || ! has_real_dev_age_recipient; then
    skip "sops decrypt verification skipped because dev .sops.yaml has no real age recipient"
    return
  fi

  if [[ ! -f "$key_file" ]]; then
    skip "sops decrypt verification skipped because private key is missing: ${key_file}"
    return
  fi

  if [[ ! -f "$sample" ]] || ! grep -q '^sops:' "$sample"; then
    skip "sops decrypt verification skipped because bootstrap-creds.enc.yaml is not SOPS-encrypted"
    return
  fi

  set +e
  SOPS_AGE_KEY_FILE="$key_file" sops --decrypt "$sample" >"$output_file" 2>"$error_file"
  status=$?
  set -e

  if [[ "$status" -eq 0 && -s "$output_file" ]]; then
    pass "sops decrypt succeeds for bootstrap-creds.enc.yaml"
  else
    fail "sops decrypt succeeds for bootstrap-creds.enc.yaml"
    if [[ -s "$error_file" ]]; then
      sed 's/^/    stderr: /' "$error_file"
    fi
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

run_sops_checks() {
  section "SOPS+age Secrets"
  assert_dev_sops_yaml_exists
  assert_dev_sops_yaml_has_creation_rule
  assert_dev_sops_yaml_has_recipient
  assert_dev_bootstrap_secret_exists
  assert_bootstrap_flux_script_exists
  assert_dev_enc_files_have_sops_metadata
  assert_sops_decrypt_works_if_tools_present
}

run_cluster_checks() {
  section "Local kind Verification Harness"
  assert_bootstrap_script_executable
  assert_bootstrap_script_help_works
  assert_bootstrap_script_required_functions
  assert_kind_cluster_creation_path_documented
  assert_flux_check_pre_in_bootstrap
  assert_bootstrap_script_idempotent
  assert_local_git_mechanism_documented
  assert_local_source_patch_concrete
  run_cluster_bootstrap_if_tools_present
}

if [[ "$FLUX_RENDER_ONLY" == true ]]; then
  run_flux_render_checks
elif [[ "$LAYOUT_ONLY" == true ]]; then
  run_layout_checks
elif [[ "$SOPS_ONLY" == true ]]; then
  run_sops_checks
elif [[ "$CLUSTER_ONLY" == true ]]; then
  run_cluster_checks
else
  run_layout_checks
  run_flux_render_checks
  run_sops_checks
  run_tool_checks
fi

section "Summary"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo ""
echo "Results: ${PASS_COUNT}/${TOTAL} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "STATUS: FAILED"
  exit 1
else
  echo "STATUS: ALL PASSED"
  exit 0
fi
