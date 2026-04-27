#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "09-image-registry" "local registry and pull-through cache"

run_validator validate-container-delivery infra/tests/validate_container_delivery_local.sh --channel local --kubeconfig "$KUBECONFIG_PATH" --tag init-109-local
docker inspect k3d-humility-local-cache-docker >/dev/null 2>&1 || e2e_fail "Docker Hub cache container missing"
e2e_pass "Docker Hub pull-through cache container exists"
e2e_finish
