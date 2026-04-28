#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "10-buildkite" "Buildkite local CI/CD"

if [[ -z "${BUILDKITE_AGENT_TOKEN:-}" ]] && ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n buildkite-agent get secret buildkite-agent-token >/dev/null 2>&1; then
  e2e_fail "Buildkite agent token is unavailable from BUILDKITE_AGENT_TOKEN or Secret/buildkite-agent-token"
fi

run_validator validate-buildkite infra/tests/validate_buildkite_cicd_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH" --tag init-109-local
e2e_finish
