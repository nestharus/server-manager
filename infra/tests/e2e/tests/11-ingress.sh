#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "11-ingress" "Kong ingress"
run_validator validate-kong-ingress infra/tests/validate_kong_ingress_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
