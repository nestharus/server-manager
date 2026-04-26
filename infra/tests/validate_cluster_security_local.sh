#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
PROVIDER_K8S_SA="system:serviceaccount:crossplane-system:provider-kubernetes"
DENY_POD="netpol-deny-minio"

usage() {
  cat <<'EOF'
Usage: validate_cluster_security_local.sh [--kubeconfig PATH]

Validates the INIT-107 local cluster security proof against an existing local
channel: PSS admission rejects a bad Pod, NetworkPolicy denies unauthorized
traffic, provider-kubernetes RBAC is namespaced, and stateful PDBs exist.
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
  output="$(kubectl_cmd apply --dry-run=server -f - 2>&1 <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: pss-should-be-rejected
  namespace: infisical-sample
spec:
  restartPolicy: Never
  containers:
    - name: bad
      image: busybox:1.37.0
      command: ["/bin/sh", "-c", "sleep 1"]
      securityContext:
        privileged: true
YAML
)"
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

  kubectl_cmd -n infisical-sample apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: ${DENY_POD}
  labels:
    app.kubernetes.io/name: ${DENY_POD}
spec:
  restartPolicy: Never
  activeDeadlineSeconds: 45
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: client
      image: busybox:1.37.0
      command:
        - /bin/sh
        - -ec
        - |
          if nc -z -w 5 minio.minio-system.svc.cluster.local 9000; then
            echo "unexpected MinIO connection succeeded"
            exit 1
          fi
          echo "MinIO connection denied as expected"
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
          memory: 32Mi
        limits:
          cpu: 50m
          memory: 64Mi
YAML

  kubectl_cmd -n infisical-sample wait "pod/${DENY_POD}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=90s >/dev/null
  log "PASS: NetworkPolicy denies unauthorized MinIO traffic from infisical-sample"
}

assert_provider_kubernetes_rbac() {
  local can_create_jobs
  local can_create_namespaces
  local can_delete_secrets

  can_create_jobs="$(kubectl_cmd auth can-i create jobs.batch -n app-cluster-system --as="$PROVIDER_K8S_SA")"
  can_create_namespaces="$(kubectl_cmd auth can-i create namespaces --as="$PROVIDER_K8S_SA")"
  can_delete_secrets="$(kubectl_cmd auth can-i delete secrets -n minio-system --as="$PROVIDER_K8S_SA")"

  [[ "$can_create_jobs" == "yes" ]] || die "provider-kubernetes cannot create jobs in app-cluster-system"
  [[ "$can_create_namespaces" == "no" ]] || die "provider-kubernetes can still create namespaces"
  [[ "$can_delete_secrets" == "no" ]] || die "provider-kubernetes can delete minio-system secrets"

  log "PASS: kubectl auth can-i create jobs.batch -n app-cluster-system --as=${PROVIDER_K8S_SA}: ${can_create_jobs}"
  log "PASS: kubectl auth can-i create namespaces --as=${PROVIDER_K8S_SA}: ${can_create_namespaces}"
  log "PASS: kubectl auth can-i delete secrets -n minio-system --as=${PROVIDER_K8S_SA}: ${can_delete_secrets}"
}

assert_pdbs() {
  kubectl_cmd -n infisical-system get pdb postgresql >/dev/null
  kubectl_cmd -n infisical-system get pdb redis-master >/dev/null
  kubectl_cmd -n minio-system get pdb minio >/dev/null
  log "PASS: PDB/postgresql, PDB/redis-master, and PDB/minio exist"
}

require_command kubectl
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
