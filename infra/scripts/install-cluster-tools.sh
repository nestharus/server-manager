#!/usr/bin/env bash
set -euo pipefail

K3D_VERSION="v5.8.3"
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

installed_k3d_version() {
  if ! command -v k3d >/dev/null 2>&1; then
    return 1
  fi

  k3d version 2>/dev/null | awk '/^k3d version / { print $3; exit }'
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

install_k3d() {
  local asset
  local expected_sha
  local url
  local tmpdir
  local tmpbin
  local actual_sha

  asset="$(detect_k3d_asset)"
  expected_sha="$(required_sha256 "$asset")"
  url="https://github.com/k3d-io/k3d/releases/download/${K3D_VERSION}/k3d-${asset}"

  command -v curl >/dev/null 2>&1 || die "curl is required to install k3d"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required to verify k3d"

  mkdir -p "$INSTALL_DIR"
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' RETURN
  tmpbin="${tmpdir}/k3d"

  echo "Downloading k3d ${K3D_VERSION} from ${url}"
  curl -fsSL "$url" -o "$tmpbin"

  actual_sha="$(sha256sum "$tmpbin" | awk '{print $1}')"
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    die "checksum mismatch for k3d-${asset}: expected ${expected_sha}, got ${actual_sha}"
  fi

  chmod 0755 "$tmpbin"
  mv "$tmpbin" "${INSTALL_DIR}/k3d"
  echo "$(color "$GREEN" "OK"): installed k3d ${K3D_VERSION} to ${INSTALL_DIR}/k3d"
}

main() {
  parse_args "$@"

  if [[ "$MODE" == "check" ]]; then
    check_k3d
    return $?
  fi

  if check_k3d; then
    return 0
  fi

  install_k3d
  check_k3d
}

main "$@"
