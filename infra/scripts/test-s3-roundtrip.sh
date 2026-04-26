#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
OBJECT_KEY=""

usage() {
  cat <<'EOF'
Usage: test-s3-roundtrip.sh [--dry-run] [--object-key KEY]

Reads the provider-neutral S3 contract from the environment:
  S3_ENDPOINT
  S3_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY
  S3_REGION
  S3_BUCKET

Performs PUT, GET, byte comparison, and DELETE against any S3-compatible
endpoint using the pinned MinIO Client (mc). --dry-run validates inputs and
tool availability without writing an object.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --object-key)
      [[ $# -ge 2 ]] || die "--object-key requires a value"
      OBJECT_KEY="$2"
      shift
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

for name in S3_ENDPOINT S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_REGION S3_BUCKET; do
  if [[ -z "${!name:-}" ]]; then
    die "${name} is required"
  fi
done

command -v mc >/dev/null 2>&1 || die "mc is required; run infra/scripts/install-cluster-tools.sh --install"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "DRY-RUN: S3 round-trip configuration valid for bucket ${S3_BUCKET} at ${S3_ENDPOINT}"
  exit 0
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

export MC_CONFIG_DIR="${tmpdir}/mc"
alias_name="roundtrip-${$}"
body_file="${tmpdir}/body.txt"
download_file="${tmpdir}/download.txt"

if [[ -z "$OBJECT_KEY" ]]; then
  OBJECT_KEY="init-104-roundtrip/$(date +%Y%m%dT%H%M%S)-${$}.txt"
fi

printf 'init-104 object storage round trip\n' >"$body_file"

mc alias set "$alias_name" "$S3_ENDPOINT" "$S3_ACCESS_KEY_ID" "$S3_SECRET_ACCESS_KEY" >/dev/null
mc cp "$body_file" "${alias_name}/${S3_BUCKET}/${OBJECT_KEY}" >/dev/null
echo "PUT ok: s3://${S3_BUCKET}/${OBJECT_KEY}"

mc cp "${alias_name}/${S3_BUCKET}/${OBJECT_KEY}" "$download_file" >/dev/null
if ! cmp -s "$body_file" "$download_file"; then
  die "GET content mismatch for s3://${S3_BUCKET}/${OBJECT_KEY}"
fi
echo "GET ok: s3://${S3_BUCKET}/${OBJECT_KEY}"

mc rm "${alias_name}/${S3_BUCKET}/${OBJECT_KEY}" >/dev/null
echo "DELETE ok: s3://${S3_BUCKET}/${OBJECT_KEY}"
