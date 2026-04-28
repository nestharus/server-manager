#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
CLUSTER_MODE=0
STATIC_ONLY=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE_DIR="${SCRIPT_DIR}/fixtures/cluster-security"
PSS_DENIED_POD_FIXTURE="${FIXTURE_DIR}/pss-privileged-pod-denied.yaml"
NETPOL_DENY_PROBE_FIXTURE="${FIXTURE_DIR}/netpol-deny-minio-probe.yaml"
RBAC_SUBJECT_FIXTURE="${FIXTURE_DIR}/rbac-subject.env"
DENY_POD="netpol-deny-minio"

# shellcheck source=/dev/null
source "$RBAC_SUBJECT_FIXTURE"

usage() {
  cat <<'EOF'
Usage: validate_cluster_security_local.sh [--cluster] [--static-only] [--kubeconfig PATH]

Validates the INIT-107 local cluster security proof against an existing local
channel: PSS admission rejects a bad Pod, NetworkPolicy denies unauthorized
traffic, provider-kubernetes RBAC is namespaced, and stateful PDBs exist.

Options:
  --cluster          Run explicit cluster runtime validation
  --static-only      Validate cluster-security test fixtures without kubectl
  --kubeconfig PATH  Kubeconfig for the local k3d channel
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)
      CLUSTER_MODE=1
      ;;
    --static-only)
      STATIC_ONLY=1
      ;;
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift
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

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  local description="$3"

  grep -Eq "$pattern" "$file" || die "${description} missing from ${file}"
}

assert_static_fixtures() {
  [[ -f "$PSS_DENIED_POD_FIXTURE" ]] || die "missing fixture: ${PSS_DENIED_POD_FIXTURE}"
  [[ -f "$NETPOL_DENY_PROBE_FIXTURE" ]] || die "missing fixture: ${NETPOL_DENY_PROBE_FIXTURE}"
  [[ -f "$RBAC_SUBJECT_FIXTURE" ]] || die "missing fixture: ${RBAC_SUBJECT_FIXTURE}"

  assert_file_contains "$PSS_DENIED_POD_FIXTURE" '^kind: Pod$' "PSS denied Pod kind"
  assert_file_contains "$PSS_DENIED_POD_FIXTURE" 'name: pss-should-be-rejected' "PSS denied Pod name"
  assert_file_contains "$PSS_DENIED_POD_FIXTURE" 'namespace: infisical-sample' "PSS denied Pod namespace"
  assert_file_contains "$PSS_DENIED_POD_FIXTURE" 'privileged: true' "PSS privileged violation"

  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'name: netpol-deny-minio' "NetworkPolicy probe Pod name"
  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'nc -z -w 5 minio\.minio-system\.svc\.cluster\.local 9000' "NetworkPolicy denied MinIO probe"
  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'unexpected MinIO connection succeeded' "NetworkPolicy positive-connection failure"
  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'runAsNonRoot: true' "NetworkPolicy probe non-root security context"
  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'allowPrivilegeEscalation: false' "NetworkPolicy probe privilege-escalation denial"
  assert_file_contains "$NETPOL_DENY_PROBE_FIXTURE" 'readOnlyRootFilesystem: true' "NetworkPolicy probe read-only filesystem"

  [[ "${PROVIDER_K8S_SA}" == "system:serviceaccount:crossplane-system:provider-kubernetes" ]] \
    || die "unexpected provider-kubernetes RBAC subject: ${PROVIDER_K8S_SA}"
  [[ "${PROVIDER_K8S_ALLOWED_CREATE_JOBS_NAMESPACE}" == "app-cluster-system" ]] \
    || die "unexpected provider-kubernetes allowed namespace: ${PROVIDER_K8S_ALLOWED_CREATE_JOBS_NAMESPACE}"
  [[ "${PROVIDER_K8S_DENIED_CREATE_NAMESPACES_EXPECTED}" == "no" ]] \
    || die "provider-kubernetes namespace-create denial fixture must expect no"
  [[ "${PROVIDER_K8S_DENIED_DELETE_SECRETS_NAMESPACE}" == "minio-system" ]] \
    || die "unexpected provider-kubernetes secret-delete denied namespace: ${PROVIDER_K8S_DENIED_DELETE_SECRETS_NAMESPACE}"
  [[ "${PROVIDER_K8S_DENIED_DELETE_SECRETS_EXPECTED}" == "no" ]] \
    || die "provider-kubernetes secret-delete denial fixture must expect no"

  log "PASS: cluster-security fixtures encode PSS, NetworkPolicy, and RBAC denial probes"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

cleanup() {
  kubectl_cmd -n infisical-sample delete pod "$DENY_POD" --ignore-not-found >/dev/null 2>&1 || true
}

trap cleanup EXIT

assert_namespace_label() {
  local namespace="$1"
  local expected="$2"
  local actual

  actual="$(kubectl_cmd get namespace "$namespace" -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}')"
  [[ "$actual" == "$expected" ]] || die "Namespace/${namespace} enforce=${actual}, expected ${expected}"
  log "PASS: Namespace/${namespace} PSS enforce=${expected}"
}

assert_pss_rejects_privileged_pod() {
  local output
  local status

  set +e
  output="$(kubectl_cmd apply --dry-run=server -f "$PSS_DENIED_POD_FIXTURE" 2>&1)"
  status=$?
  set -e

  if [[ "$status" -ne 0 ]] && grep -qi 'violates PodSecurity' <<<"$output"; then
    log "PASS: PSS restricted rejects privileged Pod in infisical-sample"
  else
    echo "$output"
    die "PSS did not reject privileged Pod in infisical-sample"
  fi
}

assert_network_policy_denies_minio_from_unauthorized_pod() {
  cleanup

  kubectl_cmd -n infisical-sample apply -f "$NETPOL_DENY_PROBE_FIXTURE" >/dev/null

  kubectl_cmd -n infisical-sample wait "pod/${DENY_POD}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=90s >/dev/null
  log "PASS: NetworkPolicy denies unauthorized MinIO traffic from infisical-sample"
}

capture_auth_can_i() {
  local result_var="$1"
  shift
  local output
  local status

  set +e
  output="$(kubectl_cmd auth can-i "$@")"
  status=$?
  set -e

  if [[ "$output" != "yes" && "$output" != "no" ]]; then
    [[ -z "$output" ]] || echo "$output"
    die "kubectl auth can-i returned unexpected output for: $*"
  fi

  if [[ "$status" -ne 0 && "$output" != "no" ]]; then
    die "kubectl auth can-i failed unexpectedly for: $*"
  fi

  printf -v "$result_var" '%s' "$output"
}

assert_provider_kubernetes_rbac() {
  local can_create_jobs
  local can_create_namespaces
  local can_delete_secrets
  local failed=0

  capture_auth_can_i can_create_jobs create jobs.batch -n "$PROVIDER_K8S_ALLOWED_CREATE_JOBS_NAMESPACE" --as="$PROVIDER_K8S_SA"
  capture_auth_can_i can_create_namespaces create namespaces --as="$PROVIDER_K8S_SA"
  capture_auth_can_i can_delete_secrets delete secrets -n "$PROVIDER_K8S_DENIED_DELETE_SECRETS_NAMESPACE" --as="$PROVIDER_K8S_SA"

  if [[ "$can_create_jobs" == "yes" ]]; then
    log "PASS: kubectl auth can-i create jobs.batch -n ${PROVIDER_K8S_ALLOWED_CREATE_JOBS_NAMESPACE} --as=${PROVIDER_K8S_SA}: ${can_create_jobs}"
  else
    echo "ERROR: provider-kubernetes cannot create jobs in app-cluster-system" >&2
    failed=1
  fi

  if [[ "$can_create_namespaces" == "$PROVIDER_K8S_DENIED_CREATE_NAMESPACES_EXPECTED" ]]; then
    log "PASS: kubectl auth can-i create namespaces --as=${PROVIDER_K8S_SA}: ${can_create_namespaces}"
  else
    echo "ERROR: provider-kubernetes can still create namespaces" >&2
    failed=1
  fi

  if [[ "$can_delete_secrets" == "$PROVIDER_K8S_DENIED_DELETE_SECRETS_EXPECTED" ]]; then
    log "PASS: kubectl auth can-i delete secrets -n ${PROVIDER_K8S_DENIED_DELETE_SECRETS_NAMESPACE} --as=${PROVIDER_K8S_SA}: ${can_delete_secrets}"
  else
    echo "ERROR: provider-kubernetes can delete minio-system secrets" >&2
    failed=1
  fi

  [[ "$failed" -eq 0 ]] || exit 1
}

assert_pdbs() {
  kubectl_cmd -n infisical-system get pdb postgresql >/dev/null
  kubectl_cmd -n infisical-system get pdb redis-master >/dev/null
  kubectl_cmd -n minio-system get pdb minio >/dev/null
  log "PASS: PDB/postgresql, PDB/redis-master, and PDB/minio exist"
}

assert_static_fixtures

if [[ "$STATIC_ONLY" -eq 1 ]]; then
  exit 0
fi

require_command kubectl
if [[ "$CLUSTER_MODE" -eq 1 ]]; then
  log "Cluster runtime mode requested"
fi
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

assert_namespace_label cert-manager baseline
assert_namespace_label crossplane-system baseline
assert_namespace_label flux-system baseline
assert_namespace_label git-system baseline
assert_namespace_label infisical-system restricted
assert_namespace_label minio-system restricted
assert_namespace_label platform-app-clusters restricted
assert_namespace_label app-cluster-system privileged

kubectl_cmd -n infisical-system get networkpolicy default-deny allow-infisical-to-postgresql allow-infisical-to-redis >/dev/null
kubectl_cmd -n minio-system get networkpolicy default-deny allow-minio-s3-ingress >/dev/null
log "PASS: NetworkPolicy objects exist for Infisical and MinIO isolation"

assert_pss_rejects_privileged_pod
assert_network_policy_denies_minio_from_unauthorized_pod
assert_provider_kubernetes_rbac
assert_pdbs
