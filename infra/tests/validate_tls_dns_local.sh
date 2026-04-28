#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
CLUSTER_MODE=0

usage() {
  cat <<'EOF'
Usage: validate_tls_dns_local.sh [--cluster] [--kubeconfig PATH]

Validates the local INIT-105 TLS/DNS proof against an existing cluster:
cert-manager availability, step-ca availability, StepClusterIssuer readiness,
sample Certificate Ready=True, and CoreDNS resolution for humility.local.

Options:
  --cluster          Run explicit cluster runtime validation
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

wait_json_condition() {
  local description="$1"
  local command_json="$2"
  local condition_type="$3"
  local attempts="${4:-120}"
  local attempt
  local payload

  for attempt in $(seq 1 "$attempts"); do
    payload="$(eval "$command_json" 2>/dev/null || true)"
    if python3 -c '
import json
import sys

condition_type = sys.argv[1]
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") != condition_type:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)
raise SystemExit(1)
' "$condition_type" <<<"$payload"
    then
      return 0
    fi
    sleep 3
  done

  echo "Timed out waiting for ${description}" >&2
  return 1
}

require_command kubectl
require_command python3
if [[ "$CLUSTER_MODE" -eq 1 ]]; then
  log "Cluster runtime mode requested"
fi
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl_cmd -n cert-manager wait deployment/cert-manager --for=condition=Available --timeout=300s >/dev/null
kubectl_cmd -n cert-manager wait deployment/cert-manager-cainjector --for=condition=Available --timeout=300s >/dev/null
kubectl_cmd -n cert-manager wait deployment/cert-manager-webhook --for=condition=Available --timeout=300s >/dev/null
log "PASS: cert-manager Deployments Available"

kubectl_cmd -n step-ca-system wait job/step-ca --for=condition=Complete --timeout=300s >/dev/null
kubectl_cmd -n step-ca-system rollout status statefulset/step-ca --timeout=300s >/dev/null
kubectl_cmd -n step-ca-system wait statefulset/step-ca --for=jsonpath='{.status.readyReplicas}'=1 --timeout=300s >/dev/null
log "PASS: step-ca bootstrap Job Complete and StatefulSet Ready"

kubectl_cmd -n step-issuer-system wait deployment/step-issuer --for=condition=Available --timeout=300s >/dev/null
kubectl_cmd -n step-issuer-system wait job/configure-step-clusterissuer --for=condition=Complete --timeout=300s >/dev/null
log "PASS: step-issuer Deployment Available and configure Job Complete"

wait_json_condition \
  "StepClusterIssuer/humility-local-step-ca Ready" \
  "kubectl_cmd get stepclusterissuer.certmanager.step.sm humility-local-step-ca -o json" \
  "Ready"
log "PASS: StepClusterIssuer/humility-local-step-ca Ready=True"

wait_json_condition \
  "Certificate/humility-local-sample Ready" \
  "kubectl_cmd -n cert-manager-test get certificate humility-local-sample -o json" \
  "Ready"
log "PASS: Certificate/humility-local-sample Ready=True"

kubectl_cmd -n cert-manager-test get secret humility-local-sample-tls -o jsonpath='{.data.tls\.crt}' >/dev/null
log "PASS: Secret/humility-local-sample-tls contains tls.crt"

kubectl_cmd -n cert-manager-test delete pod tls-dns-lookup --ignore-not-found >/dev/null
kubectl_cmd -n cert-manager-test wait --for=delete pod/tls-dns-lookup --timeout=60s >/dev/null 2>&1 || true
kubectl_cmd -n cert-manager-test run tls-dns-lookup \
  --restart=Never \
  --image=busybox:1.37.0 \
  --command -- /bin/sh -ec 'nslookup minio.minio-system.humility.local' >/dev/null
for _ in $(seq 1 60); do
  phase="$(kubectl_cmd -n cert-manager-test get pod tls-dns-lookup -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  [[ "$phase" == "Succeeded" ]] && break
  [[ "$phase" == "Failed" ]] && break
  sleep 2
done
phase="$(kubectl_cmd -n cert-manager-test get pod tls-dns-lookup -o jsonpath='{.status.phase}')"
logs="$(kubectl_cmd -n cert-manager-test logs tls-dns-lookup 2>/dev/null || true)"
kubectl_cmd -n cert-manager-test delete pod tls-dns-lookup --ignore-not-found >/dev/null
[[ "$phase" == "Succeeded" ]] || die "DNS lookup pod phase was ${phase}; logs: ${logs}"
grep -q 'minio.minio-system.humility.local' <<<"$logs" || die "DNS lookup logs did not include queried name: ${logs}"
log "PASS: CoreDNS resolves minio.minio-system.humility.local"
