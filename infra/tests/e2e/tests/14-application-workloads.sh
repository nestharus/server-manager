#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "14-application-workloads" "server-manager API and Discord workloads"
run_validator validate-application-workloads infra/tests/validate_application_workloads_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH" --tag init-113-local --skip-image-build
e2e_finish
