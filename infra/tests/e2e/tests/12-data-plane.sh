#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "12-data-plane" "CNPG and Atlas data plane"
run_validator validate-data-plane infra/tests/validate_data_plane_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
