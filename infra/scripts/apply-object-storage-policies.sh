#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
EXECUTE=0
ALIAS_NAME="humility-storage"

usage() {
  cat <<'EOF'
Usage: apply-object-storage-policies.sh [--channel local] [--alias NAME] [--execute]

Dry-run by default. Execution applies versioning, SSE-S3 default encryption,
and lifecycle expiration to the channel object-storage bucket and backup bucket
through an existing mc alias. The same script works for MinIO and Vultr Object
Storage because both expose S3-compatible bucket policy APIs.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --channel)
      [[ $# -ge 2 ]] || die "--channel requires a value"
      CHANNEL_REQUEST="$2"
      shift
      ;;
    --alias)
      [[ $# -ge 2 ]] || die "--alias requires a value"
      ALIAS_NAME="$2"
      shift
      ;;
    --execute)
      EXECUTE=1
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

command -v jq >/dev/null 2>&1 || die "jq is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

resolved="$(python3 "$RESOLVER" --channel "$CHANNEL_REQUEST")"
channel="$(jq -er '.id' <<<"$resolved")"
sample_bucket="$(jq -er '.object_storage.bucket' <<<"$resolved")"
backup_bucket="$(jq -er '.backup.bucket // empty' <<<"$resolved")"
lifecycle_days="$(jq -er '.access_policy.object_storage_policy.lifecycle_days' <<<"$resolved")"
encryption="$(jq -er '.access_policy.object_storage_policy.encryption' <<<"$resolved")"

apply_bucket() {
  local bucket="$1"
  local lifecycle_rule_id
  echo "APPLY: mc version enable ${ALIAS_NAME}/${bucket}"
  echo "APPLY: mc encrypt set ${encryption} ${ALIAS_NAME}/${bucket}"
  echo "APPLY: mc ilm rule add --expire-days ${lifecycle_days} ${ALIAS_NAME}/${bucket}"
  if [[ "$EXECUTE" -eq 1 ]]; then
    mc version enable "${ALIAS_NAME}/${bucket}"
    mc encrypt set "$encryption" "${ALIAS_NAME}/${bucket}"
    lifecycle_rule_id="$(
      mc ilm rule ls --json "${ALIAS_NAME}/${bucket}" 2>/dev/null | jq -r \
        --argjson days "$lifecycle_days" \
        'select((.expiration.days // .expiration.Days // empty) == $days) | .id // .ID // empty' \
        | head -n 1 || true
    )"
    if [[ -n "$lifecycle_rule_id" ]]; then
      mc ilm rule edit --id "$lifecycle_rule_id" --expire-days "$lifecycle_days" "${ALIAS_NAME}/${bucket}"
    else
      mc ilm rule add --expire-days "$lifecycle_days" "${ALIAS_NAME}/${bucket}"
    fi
  fi
}

if [[ "$EXECUTE" -eq 1 ]]; then
  command -v mc >/dev/null 2>&1 || die "mc is required"
fi

echo "PASS: object-storage policy resolved channel ${channel}"
apply_bucket "$sample_bucket"
if [[ -n "$backup_bucket" && "$backup_bucket" != "$sample_bucket" ]]; then
  apply_bucket "$backup_bucket"
fi

if [[ "$EXECUTE" -eq 1 ]]; then
  echo "PASS: object-storage policies applied"
fi
