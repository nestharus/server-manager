#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "08-cluster-security" "PSS, NetworkPolicy, Crossplane RBAC"
run_validator validate-cluster-security infra/tests/validate_cluster_security_local.sh --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
