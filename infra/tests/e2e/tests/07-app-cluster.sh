#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "07-app-cluster" "Crossplane AppCluster"
run_validator validate-app-clusters infra/tests/validate_app_clusters_local.sh --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
