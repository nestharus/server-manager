#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
LOCAL_RUNNER="${REPO_ROOT}/infra/scripts/run-local-buildkite-pipeline.py"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
IMAGE_TAG="init-109-local"
STATIC_ONLY=0
KEEP=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
NAMESPACE=""
PULL_IMAGE=""
IMAGE_BUILT=0

usage() {
  cat <<'EOF'
Usage: validate_buildkite_cicd_local.sh [--channel local] [--kubeconfig PATH] [--tag TAG] [--static-only] [--keep]

Validates INIT-109 Buildkite CI/CD:
  - channel cicd schema resolution
  - Buildkite pipeline and local runner
  - raw Kubernetes agent manifests
  - Infisical token path contract
  - local pipeline smoke step
  - optional image build/push and k3d Pod pull proof

Options:
  --channel <id>     Channel id to resolve (default: local)
  --kubeconfig PATH  Kubeconfig for the local k3d channel
  --tag TAG          Image tag for the local pipeline build/push step
  --static-only      Skip Docker and Kubernetes runtime proof
  --keep             Keep the runtime smoke namespace after success
  -h, --help         Show this help
EOF
}

pass() {
  echo "PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "FAIL: $1" >&2
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "SKIP: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

die() {
  fail "$*"
  finish
  exit 1
}

finish() {
  echo "RESULT: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
}

cleanup() {
  if [[ "$KEEP" -eq 0 && -n "${NAMESPACE:-}" && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" delete namespace "$NAMESPACE" --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift
        ;;
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift
        ;;
      --static-only)
        STATIC_ONLY=1
        ;;
      --keep)
        KEEP=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
    shift
  done
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    return 1
  fi
}

assert_file() {
  local path="$1"
  [[ -f "${REPO_ROOT}/${path}" ]] && pass "exists: ${path}" || die "missing: ${path}"
}

assert_executable() {
  local path="$1"
  [[ -x "${REPO_ROOT}/${path}" ]] && pass "executable: ${path}" || die "not executable: ${path}"
}

assert_contains() {
  local path="$1"
  local pattern="$2"
  local description="$3"

  if grep -q -- "$pattern" "${REPO_ROOT}/${path}"; then
    pass "$description"
  else
    die "$description"
  fi
}

assert_no_committed_token() {
  if rg -n 'bk[a-z]_[A-Za-z0-9]{20,}|BUILDKITE_AGENT_TOKEN=[^"$({ ]' \
    --glob '!infra/tests/validate_buildkite_cicd_local.sh' \
    "${REPO_ROOT}/.buildkite" "${REPO_ROOT}/gitops" "${REPO_ROOT}/infra" >/tmp/init109-token-scan.txt; then
    cat /tmp/init109-token-scan.txt >&2
    die "no Buildkite token literals committed"
  fi
  pass "no Buildkite token literals committed"
}

json_field() {
  local expression="$1"
  jq -er "$expression" <<<"$RESOLVED_JSON"
}

assert_channel_contract() {
  RESOLVED_JSON="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  [[ "$(json_field '.cicd.provider')" == "buildkite" ]] || die "cicd provider is buildkite"
  [[ "$(json_field '.cicd.agent_namespace')" == "buildkite-agent" ]] || die "agent namespace is buildkite-agent"
  [[ "$(json_field '.cicd.agent_image')" == "buildkite/agent:3.104.0" ]] || die "agent image pin"
  [[ "$(json_field '.cicd.agent_token_secret_key')" == "BUILDKITE_AGENT_TOKEN" ]] || die "token key contract"
  [[ "$(json_field '.cicd.infisical_project')" == "platform-cicd" ]] || die "Infisical project contract"
  [[ "$(json_field '.cicd.local_pipeline_file')" == ".buildkite/pipeline.yml" ]] || die "pipeline path contract"
  pass "resolved channel cicd contract"

  NAMESPACE="$(json_field '.image_registry.sample.namespace')-init-109"
  PULL_IMAGE="$(json_field '.image_registry.pull_url')/$(json_field '.image_registry.repository_prefix')/$(json_field '.image_registry.sample.app'):${IMAGE_TAG}"
}

assert_cicd_kustomization() {
  if kubectl kustomize "${REPO_ROOT}/gitops/channels/local/cicd" >/dev/null; then
    pass "cicd raw manifests kustomize"
  else
    die "cicd raw manifests kustomize"
  fi
}

run_local_pipeline_static() {
  "$PYTHON_BIN" "$LOCAL_RUNNER" --dry-run --step-key init-109-smoke --step-key registry-build-push >/tmp/init109-local-pipeline-dry-run.txt
  pass "local Buildkite pipeline dry-run"

  "$PYTHON_BIN" "$LOCAL_RUNNER" --step-key init-109-smoke >/tmp/init109-smoke.txt
  if grep -q "INIT-109 Buildkite local smoke" /tmp/init109-smoke.txt; then
    pass "sample pipeline smoke step executed"
  else
    cat /tmp/init109-smoke.txt >&2
    die "sample pipeline smoke step executed"
  fi
}

run_image_build_push() {
  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "Docker build/push skipped by --static-only"
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    skip "Docker build/push skipped; docker command missing"
    return
  fi
  if ! docker info >/dev/null 2>&1; then
    skip "Docker build/push skipped; docker daemon unavailable"
    return
  fi
  if ! command -v curl >/dev/null 2>&1; then
    skip "Docker build/push skipped; curl command missing for registry preflight"
    return
  fi
  if ! curl -fsS --max-time 2 "http://localhost:5000/v2/" >/dev/null 2>&1; then
    skip "Docker build/push skipped; local registry http://localhost:5000 is unavailable"
    return
  fi

  IMAGE_TAG="$IMAGE_TAG" "$PYTHON_BIN" "$LOCAL_RUNNER" --step-key registry-build-push
  IMAGE_BUILT=1
  pass "sample pipeline container build/push step executed"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

assert_agent_up_if_cluster_available() {
  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "cluster agent check skipped by --static-only"
    return
  fi
  if ! command -v kubectl >/dev/null 2>&1; then
    skip "cluster agent check skipped; kubectl command missing"
    return
  fi
  if [[ ! -f "$KUBECONFIG_PATH" ]]; then
    skip "cluster agent check skipped; kubeconfig not found"
    return
  fi
  if ! kubectl_cmd get namespace buildkite-agent >/dev/null 2>&1; then
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/namespace.yaml" >/dev/null
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/serviceaccount.yaml" >/dev/null
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/rbac.yaml" >/dev/null
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/configmap.yaml" >/dev/null
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/networkpolicy.yaml" >/dev/null
    kubectl_cmd apply -f "${REPO_ROOT}/gitops/channels/local/cicd/deployment.yaml" >/dev/null
  fi
  kubectl_cmd -n buildkite-agent get deployment buildkite-agent >/dev/null
  kubectl_cmd -n buildkite-agent rollout status deployment/buildkite-agent --timeout=120s >/dev/null
  pass "Buildkite agent Deployment is Available in local cluster"
}

run_cluster_pull_proof() {
  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "cluster image pull proof skipped by --static-only"
    return
  fi
  if [[ "$IMAGE_BUILT" -ne 1 ]]; then
    skip "cluster image pull proof skipped; image build/push did not run"
    return
  fi
  if ! command -v kubectl >/dev/null 2>&1; then
    skip "cluster image pull proof skipped; kubectl command missing"
    return
  fi
  if [[ ! -f "$KUBECONFIG_PATH" ]]; then
    skip "cluster image pull proof skipped; kubeconfig not found"
    return
  fi

  kubectl_cmd create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl_cmd apply -f - >/dev/null
  kubectl_cmd label namespace "$NAMESPACE" \
    pod-security.kubernetes.io/enforce=restricted \
    pod-security.kubernetes.io/warn=restricted \
    pod-security.kubernetes.io/audit=restricted \
    --overwrite >/dev/null

  kubectl_cmd -n "$NAMESPACE" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: registry-smoke
  labels:
    app.kubernetes.io/name: registry-smoke
    platform.humility.gg/init: "109"
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: registry-smoke
      image: ${PULL_IMAGE}
      imagePullPolicy: Always
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
        readOnlyRootFilesystem: true
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      resources:
        requests:
          cpu: 10m
          memory: 16Mi
        limits:
          cpu: 50m
          memory: 64Mi
YAML

  kubectl_cmd -n "$NAMESPACE" wait pod/registry-smoke --for=condition=Ready --timeout=120s >/dev/null
  if kubectl_cmd -n "$NAMESPACE" logs pod/registry-smoke | grep -q "INIT-108 registry smoke container running"; then
    pass "cluster proof: sample pipeline image pulled and ran (${PULL_IMAGE})"
  else
    kubectl_cmd -n "$NAMESPACE" describe pod/registry-smoke || true
    die "cluster proof: sample pipeline image pulled and ran"
  fi
}

main() {
  parse_args "$@"

  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  command -v jq >/dev/null 2>&1 || die "jq is required"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for manifest validation"

  assert_file ".buildkite/pipeline.yml"
  assert_file "gitops/channels/local/cicd/deployment.yaml"
  assert_file "gitops/channels/local/cicd/buildkite-agent-token-infisicalsecret.yaml"
  assert_file "infra/scripts/bootstrap-infisical-cicd.sh"
  assert_executable "infra/scripts/bootstrap-infisical-cicd.sh"
  assert_executable "infra/scripts/run-local-buildkite-pipeline.py"
  assert_contains ".buildkite/pipeline.yml" "infra/scripts/build-channel-image.sh" "pipeline reuses INIT-108 image builder"
  assert_contains "gitops/channels/local/cicd/buildkite-agent-token-infisicalsecret.yaml" "projectSlug: platform-cicd" "agent token sourced from platform-cicd"
  assert_contains "gitops/channels/local/kustomization.yaml" "  - cicd" "local GitOps root includes cicd"

  assert_no_committed_token
  assert_channel_contract
  assert_cicd_kustomization
  run_local_pipeline_static
  run_image_build_push
  assert_agent_up_if_cluster_available
  run_cluster_pull_proof

  finish
  [[ "$FAIL_COUNT" -eq 0 ]]
}

main "$@"
