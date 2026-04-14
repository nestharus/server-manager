#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
INFRA_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)

failures=0

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  failures=$((failures + 1))
}

info() {
  printf '[INFO] %s\n' "$1"
}

check_file_exists() {
  local path="$1"
  local description="$2"

  if [[ -f "${path}" ]]; then
    pass "${description}"
  else
    fail "${description} (${path} missing)"
  fi
}

check_line_pattern() {
  local file="$1"
  local pattern="$2"
  local description="$3"

  if [[ ! -f "${file}" ]]; then
    fail "${description} (${file} missing)"
    return
  fi

  if grep -Eq "${pattern}" "${file}"; then
    pass "${description}"
  else
    fail "${description}"
  fi
}

check_flat_pattern() {
  local file="$1"
  local pattern="$2"
  local description="$3"

  if [[ ! -f "${file}" ]]; then
    fail "${description} (${file} missing)"
    return
  fi

  if tr '\n' ' ' < "${file}" | grep -Eq "${pattern}"; then
    pass "${description}"
  else
    fail "${description}"
  fi
}

check_required_files() {
  check_file_exists "${INFRA_DIR}/main.tf" "infra/main.tf exists"
  check_file_exists "${INFRA_DIR}/variables.tf" "infra/variables.tf exists"
  check_file_exists "${INFRA_DIR}/cluster.tf" "infra/cluster.tf exists"
  check_file_exists "${INFRA_DIR}/environments/staging/terraform.tfvars" \
    "staging terraform.tfvars exists"
  check_file_exists "${INFRA_DIR}/environments/production/terraform.tfvars" \
    "production terraform.tfvars exists"
}

check_main_tf() {
  local main_tf="${INFRA_DIR}/main.tf"

  check_flat_pattern "${main_tf}" \
    'terraform[[:space:]]*\{.*required_version[[:space:]]*=' \
    'main.tf declares terraform.required_version'
  check_flat_pattern "${main_tf}" \
    'required_providers[[:space:]]*\{.*hcloud[[:space:]]*=[[:space:]]*\{.*source[[:space:]]*=[[:space:]]*"hetznercloud/hcloud".*version[[:space:]]*=' \
    'main.tf pins the hcloud provider source and version'
  check_flat_pattern "${main_tf}" \
    'provider[[:space:]]*"hcloud"[[:space:]]*\{' \
    'main.tf declares the hcloud provider block'
  check_flat_pattern "${main_tf}" \
    'backend[[:space:]]*"s3"[[:space:]]*\{' \
    'main.tf configures an s3 remote state backend'
  check_flat_pattern "${main_tf}" \
    'backend[[:space:]]*"s3"[[:space:]]*\{.*(endpoint|endpoints)[[:space:]]*=' \
    'main.tf uses an S3-compatible backend endpoint setting'
}

check_variables_tf() {
  local variables_tf="${INFRA_DIR}/variables.tf"

  check_flat_pattern "${variables_tf}" \
    'variable[[:space:]]*"hcloud_token"[[:space:]]*\{.*sensitive[[:space:]]*=[[:space:]]*true' \
    'variables.tf declares hcloud_token as sensitive'

  local required_vars=(
    environment
    cluster_name
    location
    control_plane_count
    worker_count
    ssh_key_ids
  )
  local var_name

  for var_name in "${required_vars[@]}"; do
    check_line_pattern "${variables_tf}" \
      "variable[[:space:]]+\"${var_name}\"[[:space:]]*\\{" \
      "variables.tf declares ${var_name}"
  done
}

check_cluster_tf() {
  local cluster_tf="${INFRA_DIR}/cluster.tf"

  check_line_pattern "${cluster_tf}" \
    'kube-hetzner' \
    'cluster.tf references the kube-hetzner module'
}

check_tfvars() {
  local staging_tfvars="${INFRA_DIR}/environments/staging/terraform.tfvars"
  local production_tfvars="${INFRA_DIR}/environments/production/terraform.tfvars"

  check_line_pattern "${staging_tfvars}" \
    '^[[:space:]]*control_plane_count[[:space:]]*=[[:space:]]*1([[:space:]]|$)' \
    'staging sets control_plane_count = 1'
  check_line_pattern "${production_tfvars}" \
    '^[[:space:]]*control_plane_count[[:space:]]*=[[:space:]]*3([[:space:]]|$)' \
    'production sets control_plane_count = 3'
  check_line_pattern "${staging_tfvars}" \
    '^[[:space:]]*cluster_name[[:space:]]*=[[:space:]]*"humility"[[:space:]]*$' \
    'staging sets cluster_name = "humility"'
  check_line_pattern "${production_tfvars}" \
    '^[[:space:]]*cluster_name[[:space:]]*=[[:space:]]*"humility"[[:space:]]*$' \
    'production sets cluster_name = "humility"'
  check_line_pattern "${staging_tfvars}" \
    '^[[:space:]]*location[[:space:]]*=[[:space:]]*"fsn1"[[:space:]]*$' \
    'staging sets location = "fsn1"'
  check_line_pattern "${production_tfvars}" \
    '^[[:space:]]*location[[:space:]]*=[[:space:]]*"fsn1"[[:space:]]*$' \
    'production sets location = "fsn1"'
}

check_for_hardcoded_secrets() {
  local tf_files=()
  local matches=""
  local key_material_matches=""

  while IFS= read -r path; do
    tf_files+=("${path}")
  done < <(find "${INFRA_DIR}" -type f \( -name '*.tf' -o -name '*.tfvars' \) ! -path '*/.terraform/*' | sort)

  if [[ ${#tf_files[@]} -eq 0 ]]; then
    fail 'Terraform source files exist for secret scanning'
    return
  fi

  matches=$(grep -nHE \
    '^[[:space:]]*[A-Za-z0-9_]*(token|secret|password|api[_-]?key|access[_-]?key)[A-Za-z0-9_]*[[:space:]]*=[[:space:]]*"[^"]+"' \
    "${tf_files[@]}" || true)

  key_material_matches=$(grep -nHE \
    '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----)' \
    "${tf_files[@]}" || true)

  if [[ -n "${matches}" || -n "${key_material_matches}" ]]; then
    fail 'No hardcoded tokens or secrets are present in .tf/.tfvars files'

    if [[ -n "${matches}" ]]; then
      printf '%s\n' "${matches}" >&2
    fi

    if [[ -n "${key_material_matches}" ]]; then
      printf '%s\n' "${key_material_matches}" >&2
    fi
  else
    pass 'No hardcoded tokens or secrets are present in .tf/.tfvars files'
  fi
}

run_terraform_validate() {
  local validator=""

  if command -v tofu >/dev/null 2>&1; then
    validator="tofu"
  elif command -v terraform >/dev/null 2>&1; then
    validator="terraform"
  else
    info 'Skipping Terraform validation because neither tofu nor terraform is installed'
    return
  fi

  if [[ ! -d "${INFRA_DIR}" ]]; then
    fail "infra directory exists for ${validator} validate"
    return
  fi

  if [[ ! -f "${INFRA_DIR}/main.tf" || ! -f "${INFRA_DIR}/variables.tf" || ! -f "${INFRA_DIR}/cluster.tf" ]]; then
    info "Skipping ${validator} validate because the root Terraform files are not all present yet"
    return
  fi

  if (cd "${INFRA_DIR}" && "${validator}" validate -no-color >/dev/null); then
    pass "${validator} validate succeeds in infra/"
  else
    fail "${validator} validate succeeds in infra/"
  fi
}

main() {
  check_required_files
  check_main_tf
  check_variables_tf
  check_cluster_tf
  check_tfvars
  check_for_hardcoded_secrets
  run_terraform_validate

  if (( failures > 0 )); then
    printf '\nValidation failed with %d issue(s).\n' "${failures}" >&2
    exit 1
  fi

  printf '\nValidation passed.\n'
}

main "$@"
