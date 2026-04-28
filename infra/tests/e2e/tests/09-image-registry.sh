#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "09-image-registry" "local registry and pull-through cache"

# shellcheck source=/dev/null
source "${REPO_ROOT}/infra/tests/fixtures/container-delivery/sample-image.env"

run_validator validate-container-delivery infra/tests/validate_container_delivery_local.sh \
  --channel "$CONTAINER_DELIVERY_CHANNEL" \
  --kubeconfig "$KUBECONFIG_PATH" \
  --tag "$CONTAINER_DELIVERY_TAG" \
  --fixture "${REPO_ROOT}/infra/tests/fixtures/container-delivery/sample-image.env"
docker inspect "$CONTAINER_DELIVERY_CACHE_CONTAINER" >/dev/null 2>&1 || e2e_fail "Docker Hub cache container missing"
e2e_pass "Docker Hub pull-through cache container exists"
e2e_finish
