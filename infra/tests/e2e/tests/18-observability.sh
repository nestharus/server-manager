#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "18-observability" "Prometheus, Loki, Alertmanager"
run_validator validate-observability infra/tests/validate_observability_local.sh --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
