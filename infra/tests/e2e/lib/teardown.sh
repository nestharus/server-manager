#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi

e2e_teardown_local() {
  echo "TEARDOWN: deleting local channel cluster and registries"
  if command -v k3d >/dev/null 2>&1 && command -v docker >/dev/null 2>&1; then
    "${REPO_ROOT}/infra/scripts/delete-local-channel.sh" --channel "${CHANNEL_ID:-local}" || true
  else
    echo "TEARDOWN: k3d or docker missing; skipping channel delete"
  fi

  if command -v docker >/dev/null 2>&1; then
    docker network rm humility-local >/dev/null 2>&1 || true
  fi
}
