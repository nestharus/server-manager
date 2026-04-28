#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
source "${REPO_ROOT}/infra/tests/fixtures/tls-dns/sample-hostname.env"
CERTIFICATE_FIXTURE="${REPO_ROOT}/infra/tests/fixtures/tls-dns/sample-certificate.json"
CERTIFICATE_NAMESPACE="$(python3 - "$CERTIFICATE_FIXTURE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle)["metadata"]["namespace"])
PY
)"

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

e2e_init "06-tls-dns" "TLS and local DNS aliases"

run_validator validate-tls-dns infra/tests/validate_tls_dns_local.sh --kubeconfig "$KUBECONFIG_PATH"
require_cluster
pod="e2e-dns-sample"
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" delete pod "$pod" --ignore-not-found >/dev/null
create_dns_lookup_pod "$pod" "$TLS_DNS_SAMPLE_HOSTNAME"
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" wait "pod/${pod}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null \
  || e2e_fail "CoreDNS did not resolve ${TLS_DNS_SAMPLE_HOSTNAME}"
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" logs "$pod" >"$(e2e_log_path "dns-sample")"
kubectl_cmd -n "$CERTIFICATE_NAMESPACE" delete pod "$pod" --ignore-not-found >/dev/null
e2e_pass "CoreDNS resolves ${TLS_DNS_SAMPLE_HOSTNAME}"
e2e_finish
