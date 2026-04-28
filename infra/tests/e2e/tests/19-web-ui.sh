#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "19-web-ui" "SPA public and authenticated admin UI"

run_validator validate-web-ui infra/tests/validate_web_ui_local.sh --kubeconfig "$KUBECONFIG_PATH" --tag init-118-local --skip-image-build
"${REPO_ROOT}/infra/tests/e2e/lib/playwright/run-browser-flow.sh" web-ui "$KUBECONFIG_PATH" "$(e2e_log_path playwright-web-ui)"
e2e_pass "Playwright completed web UI OAuth and navigation flow"
e2e_finish
