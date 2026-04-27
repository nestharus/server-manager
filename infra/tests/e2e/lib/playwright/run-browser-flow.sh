#!/usr/bin/env bash
set -euo pipefail

FLOW="${1:?flow is required}"
KUBECONFIG_PATH="${2:?kubeconfig path is required}"
LOG_FILE="${3:?log path is required}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../../.." && pwd)"
SESSION_DIR="${REPO_ROOT}/infra/tests/e2e/playwright/sessions"
mkdir -p "$SESSION_DIR" "$(dirname "$LOG_FILE")"

if [[ ! -d "${SCRIPT_DIR}/node_modules/playwright" ]]; then
  (cd "$SCRIPT_DIR" && npm install --silent) >>"$LOG_FILE" 2>&1
fi

username="sample@local.humility.local"
password="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system get secret authentik-config -o jsonpath='{.data.SAMPLE_USER_PASSWORD}' 2>/dev/null | base64 -d || true)"
if [[ -z "$password" ]]; then
  echo "missing SAMPLE_USER_PASSWORD in Secret/authentik-config" >>"$LOG_FILE"
  exit 75
fi

(
  cd "$SCRIPT_DIR"
  E2E_BROWSER_FLOW="$FLOW" \
  E2E_SESSION_DIR="$SESSION_DIR" \
  AUTHENTIK_USERNAME="$username" \
  AUTHENTIK_PASSWORD="$password" \
  node browser-flow.mjs
) >>"$LOG_FILE" 2>&1
