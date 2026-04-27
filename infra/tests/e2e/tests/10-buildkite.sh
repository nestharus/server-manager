#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "10-buildkite" "Buildkite local CI/CD"

if [[ -z "${BUILDKITE_AGENT_TOKEN:-}" ]] && ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n buildkite-agent get secret buildkite-agent-token >/dev/null 2>&1; then
  e2e_skip_flow "operator must supply BUILDKITE_AGENT_TOKEN at run time for the in-cluster agent"
fi

run_validator validate-buildkite infra/tests/validate_buildkite_cicd_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH" --tag init-109-local
e2e_finish
