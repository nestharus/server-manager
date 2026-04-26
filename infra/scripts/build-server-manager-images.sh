#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILDER="${REPO_ROOT}/infra/scripts/build-channel-image.sh"
CHANNEL_REQUEST="local"
IMAGE_TAG="init-113-local"
PRINT_ONLY=0

usage() {
  cat <<'EOF'
Usage: build-server-manager-images.sh [--channel local] [--tag TAG] [--print-only]

Builds the server-manager API and Discord daemon images through the INIT-108
channel image builder.

Options:
  --channel <id>    Channel id to resolve (default: local)
  --tag <tag>       Image tag for both app images (default: init-113-local)
  --print-only      Print resolved image names without building
  -h, --help        Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift
        ;;
      --print-only)
        PRINT_ONLY=1
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

build_image() {
  local app="$1"
  local file="$2"
  local args=(
    --channel "$CHANNEL_REQUEST"
    --app "$app"
    --tag "$IMAGE_TAG"
    --context "$REPO_ROOT"
    --file "$REPO_ROOT/$file"
  )
  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    args+=(--print-only)
  fi

  "$BUILDER" "${args[@]}"
}

main() {
  parse_args "$@"

  build_image server-manager-api containers/server-manager/Containerfile.api
  build_image server-manager-discord containers/server-manager/Containerfile.discord
}

main "$@"

