#!/usr/bin/env bash
set -euo pipefail

K3D_VERSION="v5.8.3"
FLUX_VERSION="v2.8.6"
HELM_VERSION="v3.20.2"
SOPS_VERSION="v3.12.2"
AGE_VERSION="v1.3.1"
INFISICAL_VERSION="v0.43.78"

FLUX_SHA256="c53cc990ae266f7840f64c81515d701d8821d558a9062aa4211d71b38cf044be"
HELM_SHA256="258e830a9e613c8a7a302d6059b4bb3b9758f2f3e1bb8ea0d707ce10a9a72fea"
SOPS_SHA256="14e2e1ba3bef31e74b70cf0b674f6443c80f6c5f3df15d05ffc57c34851b4998"
AGE_SHA256="bdc69c09cbdd6cf8b1f333d372a1f58247b3a33146406333e30c0f26e8f51377"
INFISICAL_SHA256="4cba7e88befff7fab44bc45bf9a0d8fe307d85748267a4c76c25deb72f38be74"

INSTALL_DIR="${HOME}/.local/bin"
NO_COLOR=0
MODE="check"

RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RESET=$'\033[0m'

usage() {
  cat <<'EOF'
Usage: install-cluster-tools.sh [--check] [--install] [--no-color]

Checks or installs the pinned local cluster toolchain.

Options:
  --check     Verify installed tool versions without side effects (default)
  --install   Install missing or mismatched tools into ~/.local/bin
  --no-color  Disable ANSI color output
  -h, --help  Show this help
EOF
}

color() {
  local code="$1"
  local text="$2"

  if [[ "${NO_COLOR}" -eq 1 ]]; then
    printf '%s' "$text"
  else
    printf '%s%s%s' "$code" "$text" "$RESET"
  fi
}

die() {
  echo "$(color "$RED" "ERROR"): $*" >&2
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --check)
        MODE="check"
        ;;
      --install)
        MODE="install"
        ;;
      --no-color)
        NO_COLOR=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
    shift
  done
}

required_sha256() {
  local os_arch="$1"

  case "$os_arch" in
    linux-386) echo "0f48e31c2ada50bd99f133b9fb19edfbba2cabce589667a1fe628a7208f721ac" ;;
    linux-amd64) echo "dbaa79a76ace7f4ca230a1ff41dc7d8a5036a8ad0309e9c54f9bf3836dbe853e" ;;
    linux-arm) echo "c4ef4e8008edb55cf347d846a7fc70af319883f9a474167689bd8af04693401d" ;;
    linux-arm64) echo "0b8110f2229631af7402fb828259330985918b08fefd38b7f1b788a1c8687216" ;;
    *) return 1 ;;
  esac
}

detect_k3d_asset() {
  local kernel
  local machine
  kernel="$(uname -s)"
  machine="$(uname -m)"

  if [[ "$kernel" != "Linux" ]]; then
    die "only Linux installs are supported by this script; found ${kernel}"
  fi

  case "$machine" in
    x86_64|amd64) echo "linux-amd64" ;;
    i386|i686) echo "linux-386" ;;
    armv6l|armv7l) echo "linux-arm" ;;
    aarch64|arm64) echo "linux-arm64" ;;
    *) die "unsupported Linux architecture: ${machine}" ;;
  esac
}

require_download_tools() {
  local tool="$1"

  command -v curl >/dev/null 2>&1 || die "curl is required to install ${tool}"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required to verify ${tool}"
}

require_tar() {
  local tool="$1"

  command -v tar >/dev/null 2>&1 || die "tar is required to install ${tool}"
}

detect_linux_amd64() {
  local tool="$1"
  local kernel
  local machine

  kernel="$(uname -s)"
  machine="$(uname -m)"

  if [[ "$kernel" != "Linux" ]]; then
    die "only Linux installs are supported for ${tool}; found ${kernel}"
  fi

  case "$machine" in
    x86_64|amd64) ;;
    *) die "only linux-amd64 installs are supported for ${tool}; found ${machine}" ;;
  esac
}

verify_sha256() {
  local file="$1"
  local expected_sha="$2"
  local description="$3"
  local actual_sha

  actual_sha="$(sha256sum "$file" | awk '{print $1}')"
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    die "checksum mismatch for ${description}: expected ${expected_sha}, got ${actual_sha}"
  fi
}

installed_k3d_version() {
  if ! command -v k3d >/dev/null 2>&1; then
    return 1
  fi

  k3d version 2>/dev/null | awk '/^k3d version / { print $3; exit }'
}

installed_flux_version() {
  if ! command -v flux >/dev/null 2>&1; then
    return 1
  fi

  flux --version 2>/dev/null | awk '/^flux version / { print "v" $3; exit }'
}

installed_helm_version() {
  if ! command -v helm >/dev/null 2>&1; then
    return 1
  fi

  helm version --short 2>/dev/null | awk '{ split($1, parts, "+"); print parts[1]; exit }'
}

installed_sops_version() {
  if ! command -v sops >/dev/null 2>&1; then
    return 1
  fi

  sops --version 2>/dev/null | awk '/^sops / { print "v" $2; exit }'
}

installed_age_version() {
  if ! command -v age >/dev/null 2>&1; then
    return 1
  fi

  age --version 2>/dev/null | awk '{ print $1; exit }'
}

installed_age_keygen_version() {
  if ! command -v age-keygen >/dev/null 2>&1; then
    return 1
  fi

  age-keygen --version 2>/dev/null | awk '{ print $1; exit }'
}

installed_infisical_version() {
  if ! command -v infisical >/dev/null 2>&1; then
    return 1
  fi

  infisical --version 2>/dev/null | awk '/^infisical version / { print "v" $3; exit } /^[0-9]+\./ { print "v" $1; exit }'
}

check_k3d() {
  local installed=""

  if installed="$(installed_k3d_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$K3D_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): k3d ${installed}"
      return 0
    fi

    echo "$(color "$YELLOW" "MISMATCH"): k3d ${installed}; expected ${K3D_VERSION}"
    return 1
  fi

  echo "$(color "$YELLOW" "MISSING"): k3d ${K3D_VERSION}"
  return 1
}

check_flux() {
  local installed=""

  if installed="$(installed_flux_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$FLUX_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): flux ${installed}"
      return 0
    fi

    echo "$(color "$YELLOW" "MISMATCH"): flux ${installed}; expected ${FLUX_VERSION}"
    return 1
  fi

  echo "$(color "$YELLOW" "MISSING"): flux ${FLUX_VERSION}"
  return 1
}

check_helm() {
  local installed=""

  if installed="$(installed_helm_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$HELM_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): helm ${installed}"
      return 0
    fi

    echo "$(color "$YELLOW" "MISMATCH"): helm ${installed}; expected ${HELM_VERSION}"
    return 1
  fi

  echo "$(color "$YELLOW" "MISSING"): helm ${HELM_VERSION}"
  return 1
}

check_sops() {
  local installed=""

  if installed="$(installed_sops_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$SOPS_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): sops ${installed}"
      return 0
    fi

    echo "$(color "$YELLOW" "MISMATCH"): sops ${installed}; expected ${SOPS_VERSION}"
    return 1
  fi

  echo "$(color "$YELLOW" "MISSING"): sops ${SOPS_VERSION}"
  return 1
}

check_age() {
  local installed=""
  local installed_keygen=""
  local status=0

  if installed="$(installed_age_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$AGE_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): age ${installed}"
    else
      echo "$(color "$YELLOW" "MISMATCH"): age ${installed}; expected ${AGE_VERSION}"
      status=1
    fi
  else
    echo "$(color "$YELLOW" "MISSING"): age ${AGE_VERSION}"
    status=1
  fi

  if installed_keygen="$(installed_age_keygen_version)" && [[ -n "$installed_keygen" ]]; then
    if [[ "$installed_keygen" == "$AGE_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): age-keygen ${installed_keygen}"
    else
      echo "$(color "$YELLOW" "MISMATCH"): age-keygen ${installed_keygen}; expected ${AGE_VERSION}"
      status=1
    fi
  else
    echo "$(color "$YELLOW" "MISSING"): age-keygen ${AGE_VERSION}"
    status=1
  fi

  return "$status"
}

check_infisical() {
  local installed=""

  if installed="$(installed_infisical_version)" && [[ -n "$installed" ]]; then
    if [[ "$installed" == "$INFISICAL_VERSION" ]]; then
      echo "$(color "$GREEN" "OK"): infisical ${installed}"
      return 0
    fi

    echo "$(color "$YELLOW" "MISMATCH"): infisical ${installed}; expected ${INFISICAL_VERSION}"
    return 1
  fi

  echo "$(color "$YELLOW" "MISSING"): infisical ${INFISICAL_VERSION}"
  return 1
}

check_all() {
  local status=0

  check_k3d || status=1
  check_flux || status=1
  check_helm || status=1
  check_sops || status=1
  check_age || status=1
  check_infisical || status=1

  return "$status"
}

install_k3d() {
  local asset
  local expected_sha
  local url
  local tmpdir
  local tmpbin

  asset="$(detect_k3d_asset)"
  expected_sha="$(required_sha256 "$asset")"
  url="https://github.com/k3d-io/k3d/releases/download/${K3D_VERSION}/k3d-${asset}"

  require_download_tools "k3d"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  tmpbin="${tmpdir}/k3d"

  echo "Downloading k3d ${K3D_VERSION} from ${url}"
  curl -fsSL "$url" -o "$tmpbin"

  verify_sha256 "$tmpbin" "$expected_sha" "k3d-${asset}"

  chmod 0755 "$tmpbin"
  mv "$tmpbin" "${INSTALL_DIR}/k3d"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed k3d ${K3D_VERSION} to ${INSTALL_DIR}/k3d"
}

install_flux() {
  local version_without_v="${FLUX_VERSION#v}"
  local url="https://github.com/fluxcd/flux2/releases/download/${FLUX_VERSION}/flux_${version_without_v}_linux_amd64.tar.gz"
  local tmpdir
  local archive
  local tmpbin

  detect_linux_amd64 "flux"
  require_download_tools "flux"
  require_tar "flux"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/flux.tar.gz"
  tmpbin="${tmpdir}/flux"

  echo "Downloading flux ${FLUX_VERSION} from ${url}"
  curl -fsSL "$url" -o "$archive"
  verify_sha256 "$archive" "$FLUX_SHA256" "flux linux-amd64 archive"

  tar -xzf "$archive" -C "$tmpdir"
  [[ -f "$tmpbin" ]] || die "flux archive did not contain ./flux"
  install -m 0755 "$tmpbin" "${INSTALL_DIR}/flux"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed flux ${FLUX_VERSION} to ${INSTALL_DIR}/flux"
}

install_helm() {
  local url="https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz"
  local tmpdir
  local archive
  local tmpbin

  detect_linux_amd64 "helm"
  require_download_tools "helm"
  require_tar "helm"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/helm.tar.gz"
  tmpbin="${tmpdir}/linux-amd64/helm"

  echo "Downloading helm ${HELM_VERSION} from ${url}"
  curl -fsSL "$url" -o "$archive"
  verify_sha256 "$archive" "$HELM_SHA256" "helm linux-amd64 archive"

  tar -xzf "$archive" -C "$tmpdir"
  [[ -f "$tmpbin" ]] || die "helm archive did not contain linux-amd64/helm"
  install -m 0755 "$tmpbin" "${INSTALL_DIR}/helm"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed helm ${HELM_VERSION} to ${INSTALL_DIR}/helm"
}

install_sops() {
  local url="https://github.com/getsops/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.linux.amd64"
  local tmpdir
  local tmpbin

  detect_linux_amd64 "sops"
  require_download_tools "sops"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  tmpbin="${tmpdir}/sops"

  echo "Downloading sops ${SOPS_VERSION} from ${url}"
  curl -fsSL "$url" -o "$tmpbin"
  verify_sha256 "$tmpbin" "$SOPS_SHA256" "sops linux-amd64 binary"

  install -m 0755 "$tmpbin" "${INSTALL_DIR}/sops"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed sops ${SOPS_VERSION} to ${INSTALL_DIR}/sops"
}

install_age() {
  local url="https://github.com/FiloSottile/age/releases/download/${AGE_VERSION}/age-${AGE_VERSION}-linux-amd64.tar.gz"
  local tmpdir
  local archive
  local tmpbin
  local tmpkeygen

  detect_linux_amd64 "age"
  require_download_tools "age"
  require_tar "age"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/age.tar.gz"

  echo "Downloading age ${AGE_VERSION} from ${url}"
  curl -fsSL "$url" -o "$archive"
  verify_sha256 "$archive" "$AGE_SHA256" "age linux-amd64 archive"

  tar -xzf "$archive" -C "$tmpdir"
  tmpbin="$(find "$tmpdir" -type f -name age | head -n 1)"
  tmpkeygen="$(find "$tmpdir" -type f -name age-keygen | head -n 1)"
  [[ -n "$tmpbin" ]] || die "age archive did not contain age"
  [[ -n "$tmpkeygen" ]] || die "age archive did not contain age-keygen"

  install -m 0755 "$tmpbin" "${INSTALL_DIR}/age"
  install -m 0755 "$tmpkeygen" "${INSTALL_DIR}/age-keygen"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed age ${AGE_VERSION} and age-keygen ${AGE_VERSION} to ${INSTALL_DIR}"
}

install_infisical() {
  local version_without_v="${INFISICAL_VERSION#v}"
  local url="https://github.com/Infisical/cli/releases/download/${INFISICAL_VERSION}/cli_${version_without_v}_linux_amd64.tar.gz"
  local tmpdir
  local archive
  local tmpbin

  detect_linux_amd64 "infisical"
  require_download_tools "infisical"
  require_tar "infisical"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/infisical.tar.gz"

  echo "Downloading infisical ${INFISICAL_VERSION} from ${url}"
  curl -fsSL "$url" -o "$archive"
  verify_sha256 "$archive" "$INFISICAL_SHA256" "infisical linux-amd64 archive"

  tar -xzf "$archive" -C "$tmpdir"
  tmpbin="$(find "$tmpdir" -type f -name infisical | head -n 1)"
  [[ -n "$tmpbin" ]] || die "infisical archive did not contain infisical"
  install -m 0755 "$tmpbin" "${INSTALL_DIR}/infisical"
  rm -rf "$tmpdir"
  echo "$(color "$GREEN" "OK"): installed infisical ${INFISICAL_VERSION} to ${INSTALL_DIR}/infisical"
}

install_missing_or_mismatched() {
  if check_k3d; then
    :
  else
    install_k3d
  fi

  if check_flux; then
    :
  else
    install_flux
  fi

  if check_helm; then
    :
  else
    install_helm
  fi

  if check_sops; then
    :
  else
    install_sops
  fi

  if check_age; then
    :
  else
    install_age
  fi

  if check_infisical; then
    :
  else
    install_infisical
  fi
}

main() {
  parse_args "$@"

  if [[ "$MODE" == "check" ]]; then
    check_all
    return $?
  fi

  install_missing_or_mismatched
  check_all
}

main "$@"
