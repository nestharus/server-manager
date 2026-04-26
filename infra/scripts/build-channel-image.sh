#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
APP_NAME=""
IMAGE_TAG=""
CONTEXT_DIR=""
CONTAINERFILE=""
PRINT_ONLY=0

usage() {
  cat <<'EOF'
Usage: build-channel-image.sh --channel local --app registry-smoke --tag init-108 --context PATH --file PATH [--print-only]

Builds a local container image with docker build, tags it for the channel image
registry, and pushes it to the channel push endpoint.

Image names follow:
  <registry>/<channel>/<app>:<tag>

Options:
  --channel <id>    Channel id to resolve (default: local)
  --app <name>      Application/image name
  --tag <tag>       Image tag
  --context <path>  Docker build context
  --file <path>     Containerfile/Dockerfile path
  --print-only      Print PUSH_IMAGE and PULL_IMAGE without building
  -h, --help        Show this help
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift
        ;;
      --app)
        [[ $# -ge 2 ]] || die "--app requires a value"
        APP_NAME="$2"
        shift
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift
        ;;
      --context)
        [[ $# -ge 2 ]] || die "--context requires a value"
        CONTEXT_DIR="$2"
        shift
        ;;
      --file)
        [[ $# -ge 2 ]] || die "--file requires a value"
        CONTAINERFILE="$2"
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

  [[ -n "$APP_NAME" ]] || die "--app is required"
  [[ -n "$IMAGE_TAG" ]] || die "--tag is required"
  [[ -n "$CONTEXT_DIR" ]] || die "--context is required"
  [[ -n "$CONTAINERFILE" ]] || die "--file is required"
}

json_field() {
  local field="$1"

  "$PYTHON_BIN" - "$RESOLVED_JSON" "$field" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
field = sys.argv[2]
registry = data["image_registry"]

if field == "id":
    print(data["id"])
elif field == "push_url":
    print(registry["push_url"])
elif field == "pull_url":
    print(registry["pull_url"])
elif field == "repository_prefix":
    print(registry["repository_prefix"])
else:
    raise SystemExit(f"unknown field: {field}")
PY
}

main() {
  parse_args "$@"

  command -v docker >/dev/null 2>&1 || die "docker is required"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  local channel_id
  local push_url
  local pull_url
  local repository_prefix
  local push_image
  local pull_image

  channel_id="$(json_field id)"
  push_url="$(json_field push_url)"
  pull_url="$(json_field pull_url)"
  repository_prefix="$(json_field repository_prefix)"
  push_image="${push_url}/${repository_prefix}/${APP_NAME}:${IMAGE_TAG}"
  pull_image="${pull_url}/${repository_prefix}/${APP_NAME}:${IMAGE_TAG}"

  echo "CHANNEL_ID=${channel_id}"
  echo "PUSH_IMAGE=${push_image}"
  echo "PULL_IMAGE=${pull_image}"

  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    return 0
  fi

  docker build -f "$CONTAINERFILE" -t "$push_image" "$CONTEXT_DIR"
  docker push "$push_image"
}

main "$@"
