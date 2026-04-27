#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "13-backup-dr" "CNPG backup and restore drill"
run_validator validate-backup-dr infra/tests/validate_backup_dr_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH"
e2e_finish
