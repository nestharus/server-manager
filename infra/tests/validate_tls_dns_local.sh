#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
CLUSTER_MODE=0
STATIC_ONLY=0
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE_DIR="${REPO_ROOT}/infra/tests/fixtures/tls-dns"
HOSTNAME_FIXTURE="${FIXTURE_DIR}/sample-hostname.env"
CERTIFICATE_FIXTURE="${FIXTURE_DIR}/sample-certificate.json"

usage() {
  cat <<'EOF'
Usage: validate_tls_dns_local.sh [--static-only] [--cluster] [--kubeconfig PATH]

Validates the local INIT-105 TLS/DNS proof against an existing cluster:
cert-manager availability, step-ca availability, StepClusterIssuer readiness,
sample Certificate Ready=True, and CoreDNS resolution for the fixture hostname.

Options:
  --static-only     Validate TLS/DNS fixtures without requiring a cluster
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
    --static-only)
      STATIC_ONLY=1
      ;;
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

load_fixtures() {
  [[ -f "$HOSTNAME_FIXTURE" ]] || die "hostname fixture not found: ${HOSTNAME_FIXTURE}"
  [[ -f "$CERTIFICATE_FIXTURE" ]] || die "Certificate fixture not found: ${CERTIFICATE_FIXTURE}"
  # shellcheck disable=SC1090
  source "$HOSTNAME_FIXTURE"
  [[ -n "${TLS_DNS_SAMPLE_HOSTNAME:-}" ]] || die "TLS_DNS_SAMPLE_HOSTNAME is empty"
}

validate_static_fixtures() {
  TLS_DNS_SAMPLE_HOSTNAME="$TLS_DNS_SAMPLE_HOSTNAME" python3 - "$CERTIFICATE_FIXTURE" <<'PY'
import json
import os
import sys

certificate_path = sys.argv[1]
sample_hostname = os.environ["TLS_DNS_SAMPLE_HOSTNAME"]

with open(certificate_path, encoding="utf-8") as handle:
    certificate = json.load(handle)

errors = []
metadata = certificate.get("metadata", {})
spec = certificate.get("spec", {})
issuer_ref = spec.get("issuerRef", {})
dns_names = spec.get("dnsNames", [])
for field, value in {
    "apiVersion": certificate.get("apiVersion"),
    "kind": certificate.get("kind"),
    "metadata.name": metadata.get("name"),
    "metadata.namespace": metadata.get("namespace"),
    "spec.secretName": spec.get("secretName"),
    "spec.issuerRef.name": issuer_ref.get("name"),
}.items():
    if not value:
        errors.append(f"{field} must be set")

if certificate.get("apiVersion") != "cert-manager.io/v1":
    errors.append("Certificate apiVersion must be cert-manager.io/v1")
if certificate.get("kind") != "Certificate":
    errors.append("fixture kind must be Certificate")
if not sample_hostname.endswith(".humility.local"):
    errors.append("sample hostname must stay under .humility.local")
if sample_hostname not in dns_names:
    errors.append("Certificate dnsNames must include TLS_DNS_SAMPLE_HOSTNAME")
if issuer_ref.get("kind") != "StepClusterIssuer":
    errors.append("issuerRef.kind must be StepClusterIssuer")
if issuer_ref.get("name") != "humility-local-step-ca":
    errors.append("issuerRef.name must be humility-local-step-ca")

serialized = json.dumps(certificate, sort_keys=True).lower()
for forbidden in ("acme", "cloudflare", "letsencrypt"):
    if forbidden in serialized:
        errors.append(f"production DNS/ACME marker is out of scope: {forbidden}")

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)
PY
}

certificate_field() {
  python3 - "$CERTIFICATE_FIXTURE" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)

for part in sys.argv[2].split("."):
    value = value[part]

print(value)
PY
}

create_dns_lookup_pod() {
  local pod_name="$1"
  local hostname="$2"

  python3 - "$pod_name" "$hostname" <<'PY' | kubectl_cmd -n "$CERTIFICATE_NAMESPACE" create -f - >/dev/null
import json
import sys

pod_name = sys.argv[1]
hostname = sys.argv[2]
print(json.dumps({
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "name": pod_name,
    },
    "spec": {
        "restartPolicy": "Never",
        "securityContext": {
            "runAsNonRoot": True,
            "runAsUser": 65532,
            "runAsGroup": 65532,
            "seccompProfile": {
                "type": "RuntimeDefault",
            },
        },
        "containers": [{
            "name": "lookup",
            "image": "busybox:1.37.0",
            "command": ["/bin/sh", "-ec", f"nslookup {hostname}"],
            "securityContext": {
                "allowPrivilegeEscalation": False,
                "capabilities": {
                    "drop": ["ALL"],
                },
            },
        }],
    },
}))
PY
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

require_command python3
load_fixtures
validate_static_fixtures
log "PASS: TLS/DNS fixtures define local sample Certificate and hostname"
if [[ "$STATIC_ONLY" -eq 1 ]]; then
  exit 0
fi

require_command kubectl
if [[ "$CLUSTER_MODE" -eq 1 ]]; then
  log "Cluster runtime mode requested"
fi
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

CERTIFICATE_NAMESPACE="$(certificate_field metadata.namespace)"
CERTIFICATE_NAME="$(certificate_field metadata.name)"
CERTIFICATE_SECRET="$(certificate_field spec.secretName)"

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

kubectl_cmd apply -f "$CERTIFICATE_FIXTURE" >/dev/null
log "PASS: sample Certificate fixture applied"

wait_json_condition \
  "StepClusterIssuer/humility-local-step-ca Ready" \
  "kubectl_cmd get stepclusterissuer.certmanager.step.sm humility-local-step-ca -o json" \
  "Ready"
log "PASS: StepClusterIssuer/humility-local-step-ca Ready=True"

wait_json_condition \
  "Certificate/${CERTIFICATE_NAME} Ready" \
  "kubectl_cmd -n ${CERTIFICATE_NAMESPACE} get certificate ${CERTIFICATE_NAME} -o json" \
  "Ready"
log "PASS: Certificate/${CERTIFICATE_NAME} Ready=True"

kubectl_cmd -n "$CERTIFICATE_NAMESPACE" get secret "$CERTIFICATE_SECRET" -o jsonpath='{.data.tls\.crt}' >/dev/null
log "PASS: Secret/${CERTIFICATE_SECRET} contains tls.crt"

kubectl_cmd -n "$CERTIFICATE_NAMESPACE" delete pod tls-dns-lookup --ignore-not-found >/dev/null
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" wait --for=delete pod/tls-dns-lookup --timeout=60s >/dev/null 2>&1 || true
create_dns_lookup_pod tls-dns-lookup "$TLS_DNS_SAMPLE_HOSTNAME"
for _ in $(seq 1 60); do
  phase="$(kubectl_cmd -n "$CERTIFICATE_NAMESPACE" get pod tls-dns-lookup -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  [[ "$phase" == "Succeeded" ]] && break
  [[ "$phase" == "Failed" ]] && break
  sleep 2
done
phase="$(kubectl_cmd -n "$CERTIFICATE_NAMESPACE" get pod tls-dns-lookup -o jsonpath='{.status.phase}')"
logs="$(kubectl_cmd -n "$CERTIFICATE_NAMESPACE" logs tls-dns-lookup 2>/dev/null || true)"
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" delete pod tls-dns-lookup --ignore-not-found >/dev/null
[[ "$phase" == "Succeeded" ]] || die "DNS lookup pod phase was ${phase}; logs: ${logs}"
grep -Fq "$TLS_DNS_SAMPLE_HOSTNAME" <<<"$logs" || die "DNS lookup logs did not include queried name: ${logs}"
log "PASS: CoreDNS resolves ${TLS_DNS_SAMPLE_HOSTNAME}"
