#!/usr/bin/env bash
set -euo pipefail

# INIT-009 SLICE-031 GitOps toolchain installer.
#
# Pinned minimum versions:
# - flux >= 2.8.0
# - kind >= 0.31.0
# - sops >= 3.10.0
# - age >= 1.3.0
# - age-keygen >= 1.3.0
# - kubectl >= 1.31.0
# - embedded kubectl Kustomize >= 5.7.1
#
# Official upstream release assets and SHA256 pins:
# - flux:
#   https://github.com/fluxcd/flux2/releases/download/v2.8.0/flux_2.8.0_linux_amd64.tar.gz
#   SHA256 from flux_2.8.0_checksums.txt:
#   5339d6a6f85be36238480308458c86fc9a839821a80c7a55f1baf12151b47fd6
# - kind:
#   https://github.com/kubernetes-sigs/kind/releases/download/v0.31.0/kind-linux-amd64
#   SHA256 from kind-linux-amd64.sha256sum:
#   eb244cbafcc157dff60cf68693c14c9a75c4e6e6fedaf9cd71c58117cb93e3fa
# - sops:
#   https://github.com/getsops/sops/releases/download/v3.10.0/sops-v3.10.0.linux.amd64
#   SHA256 from sops-v3.10.0.checksums.txt:
#   0aec146367f4a4cc825ae32f2db344cd41c162e96a47bfeae7fca4ca5d2e0712
# - age and age-keygen:
#   https://github.com/FiloSottile/age/releases/download/v1.3.0/age-v1.3.0-linux-amd64.tar.gz
#   SHA256 computed from the official release asset:
#   2635f17e469b8c829055151dcbf77effe1fbefe182cb7b308aee5d0e5d923aae

readonly FLUX_VERSION="2.8.0"
readonly KIND_VERSION="0.31.0"
readonly SOPS_VERSION="3.10.0"
readonly AGE_VERSION="1.3.0"
readonly KUBECTL_MIN="1.31.0"
readonly KUSTOMIZE_MIN="5.7.1"

readonly FLUX_URL="https://github.com/fluxcd/flux2/releases/download/v${FLUX_VERSION}/flux_${FLUX_VERSION}_linux_amd64.tar.gz"
readonly FLUX_SHA256="5339d6a6f85be36238480308458c86fc9a839821a80c7a55f1baf12151b47fd6"

readonly KIND_URL="https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/kind-linux-amd64"
readonly KIND_SHA256="eb244cbafcc157dff60cf68693c14c9a75c4e6e6fedaf9cd71c58117cb93e3fa"

readonly SOPS_URL="https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64"
readonly SOPS_SHA256="0aec146367f4a4cc825ae32f2db344cd41c162e96a47bfeae7fca4ca5d2e0712"

readonly AGE_URL="https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz"
readonly AGE_SHA256="2635f17e469b8c829055151dcbf77effe1fbefe182cb7b308aee5d0e5d923aae"

readonly KUBECTL_RELEASE_URL="https://github.com/kubernetes/kubernetes/releases"

CHECK_ONLY=false
USE_COLOR=true
TMP_ROOT=""
declare -a FAILURES=()

usage() {
  cat <<'USAGE'
Usage: install-tools.sh [--check] [--no-color]

Installs or verifies the INIT-009 GitOps toolchain.

Options:
  --check     Verify installed versions only. Does not download or install.
  --no-color  Disable ANSI color in output.
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --check)
      CHECK_ONLY=true
      ;;
    --no-color)
      USE_COLOR=false
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

if [[ ! -t 1 ]]; then
  USE_COLOR=false
fi

color() {
  local code="$1"
  if [[ "$USE_COLOR" == true ]]; then
    printf '\033[%sm' "$code"
  fi
}

reset_color() {
  if [[ "$USE_COLOR" == true ]]; then
    printf '\033[0m'
  fi
}

ok() {
  color "32"
  printf 'OK'
  reset_color
}

bad() {
  color "31"
  printf 'FAIL'
  reset_color
}

install_dir() {
  if [[ "${EUID}" -eq 0 ]]; then
    printf '/usr/local/bin\n'
  else
    printf '%s/.local/bin\n' "${HOME}"
  fi
}

require_linux_amd64() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"

  if [[ "$os" != "Linux" ]]; then
    echo "ERROR: this installer is Linux-first and currently supports Linux only; found ${os}" >&2
    exit 1
  fi

  if [[ "$arch" != "x86_64" && "$arch" != "amd64" ]]; then
    echo "ERROR: this installer pins linux/amd64 release assets only; found ${arch}" >&2
    exit 1
  fi
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: required command not found: ${command_name}" >&2
    exit 1
  fi
}

extract_semver() {
  awk 'match($0, /v?[0-9]+(\.[0-9]+){1,2}/) {
    version = substr($0, RSTART, RLENGTH)
    sub(/^v/, "", version)
    print version
    exit
  }'
}

normalize_version_part() {
  local value="$1"
  value="${value%%[^0-9]*}"
  if [[ -z "$value" ]]; then
    value=0
  fi
  printf '%s\n' "$value"
}

version_ge() {
  local current="$1"
  local required="$2"
  local current_parts required_parts i current_part required_part

  IFS='.' read -r -a current_parts <<<"$current"
  IFS='.' read -r -a required_parts <<<"$required"

  for i in 0 1 2; do
    current_part="$(normalize_version_part "${current_parts[$i]:-0}")"
    required_part="$(normalize_version_part "${required_parts[$i]:-0}")"

    if ((10#$current_part > 10#$required_part)); then
      return 0
    fi
    if ((10#$current_part < 10#$required_part)); then
      return 1
    fi
  done

  return 0
}

tool_path() {
  command -v "$1" 2>/dev/null || true
}

tool_version() {
  local tool="$1"
  local path output

  case "$tool" in
    kustomize)
      if ! command -v kubectl >/dev/null 2>&1; then
        return 1
      fi
      output="$(kubectl version --client=true --output=yaml 2>&1 || true)"
      awk -F': ' '/kustomizeVersion:/ { gsub(/"/, "", $2); sub(/^v/, "", $2); print $2; exit }' <<<"$output"
      return
      ;;
  esac

  path="$(tool_path "$tool")"

  if [[ -z "$path" ]]; then
    return 1
  fi

  case "$tool" in
    flux)
      output="$("$path" --version 2>&1 || true)"
      ;;
    kind)
      output="$("$path" version 2>&1 || true)"
      ;;
    sops)
      output="$("$path" --version 2>&1 || true)"
      ;;
    age|age-keygen)
      output="$("$path" --version 2>&1 || true)"
      ;;
    kubectl)
      output="$("$path" version --client=true --output=yaml 2>&1 || true)"
      awk -F': ' '/gitVersion:/ { gsub(/"/, "", $2); sub(/^v/, "", $2); print $2; exit }' <<<"$output"
      return
      ;;
    *)
      return 1
      ;;
  esac

  extract_semver <<<"$output"
}

record_failure() {
  FAILURES+=("$1")
}

check_tool() {
  local tool="$1"
  local required="$2"
  local version path

  path="$(tool_path "$tool")"
  if [[ -z "$path" ]]; then
    printf '  [%s] %-10s missing; requires >= %s\n' "$(bad)" "$tool" "$required"
    record_failure "${tool}: missing (requires >= ${required})"
    return
  fi

  version="$(tool_version "$tool" || true)"
  if [[ -z "$version" ]]; then
    printf '  [%s] %-10s installed at %s, but version could not be parsed; requires >= %s\n' "$(bad)" "$tool" "$path" "$required"
    record_failure "${tool}: version could not be parsed (requires >= ${required})"
    return
  fi

  if version_ge "$version" "$required"; then
    printf '  [%s] %-10s %s at %s (requires >= %s)\n' "$(ok)" "$tool" "$version" "$path" "$required"
  else
    printf '  [%s] %-10s %s at %s; requires >= %s\n' "$(bad)" "$tool" "$version" "$path" "$required"
    record_failure "${tool}: ${version} is below ${required}"
  fi
}

check_kustomize() {
  local version

  if ! command -v kubectl >/dev/null 2>&1; then
    printf '  [%s] %-10s missing because kubectl is missing; requires >= %s\n' "$(bad)" "kustomize" "$KUSTOMIZE_MIN"
    record_failure "embedded kustomize: kubectl missing (requires >= ${KUSTOMIZE_MIN})"
    return
  fi

  version="$(tool_version kustomize || true)"
  if [[ -z "$version" ]]; then
    printf '  [%s] %-10s version could not be parsed from kubectl; requires >= %s\n' "$(bad)" "kustomize" "$KUSTOMIZE_MIN"
    record_failure "embedded kustomize: version could not be parsed (requires >= ${KUSTOMIZE_MIN})"
    return
  fi

  if version_ge "$version" "$KUSTOMIZE_MIN"; then
    printf '  [%s] %-10s %s from kubectl (requires >= %s)\n' "$(ok)" "kustomize" "$version" "$KUSTOMIZE_MIN"
  else
    printf '  [%s] %-10s %s from kubectl; requires >= %s\n' "$(bad)" "kustomize" "$version" "$KUSTOMIZE_MIN"
    record_failure "embedded kustomize: ${version} is below ${KUSTOMIZE_MIN}"
  fi
}

check_all() {
  FAILURES=()

  echo "Required GitOps toolchain:"
  check_tool flux "$FLUX_VERSION"
  check_tool kind "$KIND_VERSION"
  check_tool sops "$SOPS_VERSION"
  check_tool age "$AGE_VERSION"
  check_tool age-keygen "$AGE_VERSION"
  check_tool kubectl "$KUBECTL_MIN"
  check_kustomize

  if [[ "${#FAILURES[@]}" -gt 0 ]]; then
    echo ""
    echo "Missing or below-minimum tools:"
    printf '  - %s\n' "${FAILURES[@]}"
    echo "STATUS: FAILED"
    return 1
  fi

  echo "STATUS: OK"
  return 0
}

needs_install() {
  local tool="$1"
  local required="$2"
  local version

  if ! command -v "$tool" >/dev/null 2>&1; then
    return 0
  fi

  version="$(tool_version "$tool" || true)"
  if [[ -z "$version" ]]; then
    return 0
  fi

  if version_ge "$version" "$required"; then
    return 1
  fi

  return 0
}

download_verified() {
  local url="$1"
  local expected_sha="$2"
  local output="$3"
  local actual_sha

  echo "Downloading ${url}"
  curl -fsSL -o "$output" "$url"

  actual_sha="$(sha256sum "$output" | awk '{ print $1 }')"
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "ERROR: checksum mismatch for ${url}" >&2
    echo "ERROR: expected ${expected_sha}" >&2
    echo "ERROR: actual   ${actual_sha}" >&2
    exit 1
  fi

  echo "Verified SHA256 ${actual_sha}"
}

install_binary() {
  local source_path="$1"
  local binary_name="$2"
  local directory
  directory="$(install_dir)"

  mkdir -p "$directory"
  install -m 0755 "$source_path" "${directory}/${binary_name}"
  echo "Installed ${binary_name} to ${directory}/${binary_name}"
}

install_flux() {
  local archive extract_dir
  archive="${TMP_ROOT}/flux.tar.gz"
  extract_dir="${TMP_ROOT}/flux"

  download_verified "$FLUX_URL" "$FLUX_SHA256" "$archive"
  mkdir -p "$extract_dir"
  tar -xzf "$archive" -C "$extract_dir" flux
  install_binary "${extract_dir}/flux" flux
}

install_kind() {
  local binary
  binary="${TMP_ROOT}/kind"

  download_verified "$KIND_URL" "$KIND_SHA256" "$binary"
  install_binary "$binary" kind
}

install_sops() {
  local binary
  binary="${TMP_ROOT}/sops"

  download_verified "$SOPS_URL" "$SOPS_SHA256" "$binary"
  install_binary "$binary" sops
}

install_age() {
  local archive extract_dir
  archive="${TMP_ROOT}/age.tar.gz"
  extract_dir="${TMP_ROOT}/age"

  download_verified "$AGE_URL" "$AGE_SHA256" "$archive"
  mkdir -p "$extract_dir"
  tar -xzf "$archive" -C "$extract_dir"
  install_binary "${extract_dir}/age/age" age
  install_binary "${extract_dir}/age/age-keygen" age-keygen
}

install_all() {
  local target_dir
  target_dir="$(install_dir)"
  echo "Installing missing or below-minimum GitOps tools to ${target_dir}"
  echo "kubectl is a hard prerequisite and is checked only; source: ${KUBECTL_RELEASE_URL}"

  if needs_install flux "$FLUX_VERSION"; then
    install_flux
  else
    echo "flux already satisfies >= ${FLUX_VERSION}"
  fi

  if needs_install kind "$KIND_VERSION"; then
    install_kind
  else
    echo "kind already satisfies >= ${KIND_VERSION}"
  fi

  if needs_install sops "$SOPS_VERSION"; then
    install_sops
  else
    echo "sops already satisfies >= ${SOPS_VERSION}"
  fi

  if needs_install age "$AGE_VERSION" || needs_install age-keygen "$AGE_VERSION"; then
    install_age
  else
    echo "age and age-keygen already satisfy >= ${AGE_VERSION}"
  fi
}

require_linux_amd64
require_command curl
require_command sha256sum

if [[ "$CHECK_ONLY" == true ]]; then
  check_all
  exit $?
fi

require_command tar
require_command install

TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

install_all
echo ""
check_all
