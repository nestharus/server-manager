#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "16-access-policy" "Cedar allow and deny policy"
run_validator validate-access-policy infra/tests/validate_access_policy_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
