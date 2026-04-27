#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "05-storage" "MinIO object storage"
run_validator validate-object-storage infra/tests/validate_object_storage_local.sh --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
