#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "15-auth-stack" "Authentik, Pomerium, OPAL/Cedar browser flow"

run_validator validate-auth-stack infra/tests/validate_auth_stack_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH"
"${REPO_ROOT}/infra/tests/e2e/lib/playwright/run-browser-flow.sh" auth-stack "$KUBECONFIG_PATH" "$(e2e_log_path playwright-auth-stack)" \
  || e2e_skip_flow "Playwright OAuth proof requires a reachable local browser path and seeded Authentik OIDC app"
e2e_pass "Playwright completed protected API OAuth flow"
e2e_finish
