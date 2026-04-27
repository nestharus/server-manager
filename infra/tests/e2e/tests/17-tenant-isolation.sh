#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "17-tenant-isolation" "tenant isolation"
run_validator validate-tenant-isolation infra/tests/validate_tenant_isolation_local.sh --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
