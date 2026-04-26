#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="humility-local"
OUT_DIR=""
IMAGE="busybox:1.36.1"

usage() {
  cat <<'EOF'
Usage: snapshot-k3d-volumes.sh [--cluster humility-local] [--out DIR] [--image IMAGE]

Creates gzip tar archives for Docker volumes owned by the local k3d control
cluster. The default output is .tmp/k3d-volume-snapshots/<cluster>/<timestamp>.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)
      [[ $# -ge 2 ]] || die "--cluster requires a value"
      CLUSTER_NAME="$2"
      shift 2
      ;;
    --out)
      [[ $# -ge 2 ]] || die "--out requires a value"
      OUT_DIR="$2"
      shift 2
      ;;
    --image)
      [[ $# -ge 2 ]] || die "--image requires a value"
      IMAGE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

command -v docker >/dev/null 2>&1 || die "missing required command: docker"

if [[ -z "$OUT_DIR" ]]; then
  repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
  OUT_DIR="${repo_root}/.tmp/k3d-volume-snapshots/${CLUSTER_NAME}/$(date -u +%Y%m%d%H%M%S)"
fi

mkdir -p "$OUT_DIR"

mapfile -t volumes < <(
  {
    docker volume ls -q --filter "label=k3d.cluster=${CLUSTER_NAME}" 2>/dev/null || true
    docker volume ls -q | grep -E "^k3d-${CLUSTER_NAME}-(server|agent)-[0-9]+$" || true
  } | sort -u
)

[[ "${#volumes[@]}" -gt 0 ]] || die "no Docker volumes found for k3d cluster ${CLUSTER_NAME}"

for volume in "${volumes[@]}"; do
  docker volume inspect "$volume" >/dev/null
  archive="${OUT_DIR}/${volume}.tar.gz"
  docker run --rm \
    -v "${volume}:/volume:ro" \
    -v "${OUT_DIR}:/backup" \
    "$IMAGE" \
    tar -czf "/backup/$(basename "$archive")" -C /volume .
  printf 'PASS: snapshotted %s -> %s\n' "$volume" "$archive"
done

printf 'PROOF: k3d_volume_snapshot_dir=%s count=%s\n' "$OUT_DIR" "${#volumes[@]}"
