#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "06-tls-dns" "TLS and local DNS aliases"

run_validator validate-tls-dns infra/tests/validate_tls_dns_local.sh --kubeconfig "$KUBECONFIG_PATH"
require_cluster
for host in web.local.humility.local api.local.humility.local minio.local.humility.local; do
  pod="e2e-dns-${host%%.*}"
  kubectl_cmd -n cert-manager-test delete pod "$pod" --ignore-not-found >/dev/null
  kubectl_cmd -n cert-manager-test run "$pod" --restart=Never --image=busybox:1.37.0 \
    --command -- nslookup "$host" >/dev/null
  kubectl_cmd -n cert-manager-test wait "pod/${pod}" --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s >/dev/null \
    || e2e_fail "CoreDNS did not resolve ${host}"
  kubectl_cmd -n cert-manager-test logs "$pod" >"$(e2e_log_path "dns-${host%%.*}")"
  kubectl_cmd -n cert-manager-test delete pod "$pod" --ignore-not-found >/dev/null
  e2e_pass "CoreDNS resolves ${host}"
done
e2e_finish
