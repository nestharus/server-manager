#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
PORT_FORWARD_PIDS=()
TMP_DIR="$(mktemp -d)"

usage() {
  cat <<'EOF'
Usage: validate_observability_local.sh [--kubeconfig PATH] [--static-only]

Validates INIT-117 observability. Static checks cover channel contract,
raw manifests, ServiceMonitors, Grafana dashboards, alerts, Infisical secrets,
and MinIO-backed Loki config. Runtime checks prove Pods are Ready, Prometheus
has active targets, Grafana has dashboards, Alertmanager accepts a sample alert,
and Loki stores a sample log line.
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

finish() {
  echo "RESULT: pass=${PASS_COUNT} fail=${FAIL_COUNT} skip=${SKIP_COUNT}"
}

die() {
  fail "$*"
  finish
  exit 1
}

cleanup() {
  if [[ "${#PORT_FORWARD_PIDS[@]}" -gt 0 ]]; then
    for pid in "${PORT_FORWARD_PIDS[@]}"; do
      kill "$pid" >/dev/null 2>&1 || true
    done
  fi
  rm -rf "$TMP_DIR"
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kubeconfig)
      [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
      KUBECONFIG_PATH="$2"
      shift
      ;;
    --static-only)
      STATIC_ONLY=1
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

command -v jq >/dev/null 2>&1 || die "jq is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v rg >/dev/null 2>&1 || die "rg is required"
python3 -c "import yaml" 2>/dev/null || die "python3 PyYAML module is required"

OBS_DIR="${REPO_ROOT}/gitops/channels/local/observability"
OBS_CONTRACT="${REPO_ROOT}/infra/tests/fixtures/contracts/observability_contract.yml"
resolved="$(python3 "$RESOLVER" --channel local)"

jq -e '
  .observability.namespace == "observability-system" and
  .observability.prometheus.image == "prom/prometheus:v2.54.1" and
  .observability.grafana.image == "grafana/grafana:11.2.0" and
  .observability.alertmanager.image == "prom/alertmanager:v0.27.0" and
  .observability.loki.image == "grafana/loki:3.1.1" and
  .observability.otel_collector.image == "otel/opentelemetry-collector-contrib:0.106.1" and
  .observability.object_storage.provider == "minio" and
  .observability.object_storage.bucket == "humility-local-observability" and
  .observability.object_storage.infisical_project == "platform-storage" and
  .observability.tenant_label == "platform.humility.gg/tenant"
' <<<"$resolved" >/dev/null || die "observability channel contract"
pass "resolved observability channel contract"

expected_monitors="$(python3 - "$OBS_CONTRACT" <<'PY'
import json
import sys
import yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["scrape_targets"]))
PY
)"
jq -e --argjson expected "$expected_monitors" '.observability.service_monitors == $expected' <<<"$resolved" >/dev/null || die "observability ServiceMonitor contract"
pass "observability ServiceMonitor contract"

expected_dashboards="$(python3 - "$OBS_CONTRACT" <<'PY'
import json
import sys
import yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["dashboards"]["required_uids"]))
PY
)"
jq -e --argjson expected "$expected_dashboards" '.observability.dashboards == $expected' <<<"$resolved" >/dev/null || die "observability dashboard contract"
pass "observability dashboard contract"

expected_alerts="$(python3 - "$OBS_CONTRACT" <<'PY'
import json
import sys
import yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["sample_alerts"]))
PY
)"
jq -e --argjson expected "$expected_alerts" '.observability.alerts == $expected' <<<"$resolved" >/dev/null || die "observability alert contract"
pass "observability alert contract"

if command -v kubectl >/dev/null 2>&1; then
  render_tmp="${TMP_DIR}/observability-render.yaml"
  kubectl kustomize "$OBS_DIR" >"$render_tmp"
  grep -q 'kind: Deployment' "$render_tmp" || die "rendered observability manifests missing Deployment"
  grep -q 'kind: DaemonSet' "$render_tmp" || die "rendered observability manifests missing DaemonSet"
  grep -q 'kind: ServiceMonitor' "$render_tmp" || die "rendered observability manifests missing ServiceMonitor"
  pass "observability raw manifests kustomize"
else
  die "kubectl is required for static kustomize validation"
fi

helm_scan_file="${TMP_DIR}/helm-scan.txt"
if rg -n 'kind: HelmRelease|helm.toolkit.fluxcd.io|HelmRepository|helm-controller' "$OBS_DIR" >"$helm_scan_file"; then
  cat "$helm_scan_file" >&2
  die "observability manifests avoid helm-controller resources"
fi
pass "observability manifests avoid helm-controller resources"

python3 - "$OBS_DIR" <<'PY' || die "ServiceMonitor resources cover all required targets"
import sys
from pathlib import Path
import yaml

docs = [
    doc
    for doc in yaml.safe_load_all((Path(sys.argv[1]) / "service-monitors/service-monitors.yaml").read_text())
    if isinstance(doc, dict)
]
names = [doc["metadata"]["name"] for doc in docs if doc["kind"] == "ServiceMonitor"]
expected = ["flux","crossplane","cert-manager","infisical","minio","cnpg","kong","pomerium","authentik","opal","server-manager-api","buildkite-agent"]
assert names == expected, names
for doc in docs:
    if doc["kind"] != "ServiceMonitor":
        continue
    spec = doc["spec"]
    assert spec.get("namespaceSelector", {}).get("matchNames"), doc["metadata"]["name"]
    assert spec.get("selector"), doc["metadata"]["name"]
    endpoints = spec.get("endpoints")
    assert isinstance(endpoints, list) and endpoints, doc["metadata"]["name"]
    for endpoint in endpoints:
        assert endpoint.get("port"), doc["metadata"]["name"]
        assert endpoint.get("interval"), doc["metadata"]["name"]
PY
pass "ServiceMonitor resources cover all required targets"

grep -q 'bucketnames: humility-local-observability' "$OBS_DIR/loki/configmap.yaml" || die "Loki uses observability MinIO bucket"
grep -q 'endpoint: minio.minio-system.svc.cluster.local:9000' "$OBS_DIR/loki/configmap.yaml" || die "Loki uses MinIO endpoint"
grep -q 'name: loki-object-storage' "$OBS_DIR/loki/deployment.yaml" || die "Loki credentials are Secret-backed"
grep -q 'projectSlug: platform-storage' "$OBS_DIR/secrets/observability-infisicalsecret.yaml" || die "observability credentials are Infisical-managed"
pass "Loki uses MinIO and Infisical-managed credentials"

grep -q 'label_values(up, tenant)' "$OBS_DIR/dashboards/grafana-dashboards.yaml" || die "Grafana dashboards expose tenant variable"
grep -q '"uid": "flux-gitops-health"' "$OBS_DIR/dashboards/grafana-dashboards.yaml" || die "Flux dashboard exists"
grep -q '"uid": "cnpg"' "$OBS_DIR/dashboards/grafana-dashboards.yaml" || die "CNPG dashboard exists"
grep -q '"uid": "kong-request-rate"' "$OBS_DIR/dashboards/grafana-dashboards.yaml" || die "Kong dashboard exists"
grep -q '"uid": "cedar-policy-decisions"' "$OBS_DIR/dashboards/grafana-dashboards.yaml" || die "Cedar dashboard exists"
pass "tenant-aware sample dashboards exist"

grep -q 'alert: PodCrashLooping' "$OBS_DIR/prometheus/rules-configmap.yaml" || die "PodCrashLooping alert exists"
grep -q 'alert: ClusterDown' "$OBS_DIR/prometheus/rules-configmap.yaml" || die "ClusterDown alert exists"
grep -q 'alert: CertificateExpiringSoon' "$OBS_DIR/prometheus/rules-configmap.yaml" || die "CertificateExpiringSoon alert exists"
pass "sample alerts exist"

python3 - "$OBS_DIR" "$OBS_CONTRACT" <<'PY' || die "observability NetworkPolicies do not isolate operator webhooks"
import sys
from pathlib import Path
import yaml

obs_dir = Path(sys.argv[1])
contract = yaml.safe_load(Path(sys.argv[2]).read_text())
guard = contract["webhook_isolation_guard"]
forbidden_source = guard["forbidden_source_namespace"]
webhook_namespaces = set(guard["webhook_namespaces"])
offending = []

for path in sorted(obs_dir.glob("**/*.yaml")):
    docs = yaml.safe_load_all(path.read_text())
    for doc in docs:
        if not isinstance(doc, dict) or doc.get("kind") != "NetworkPolicy":
            continue
        metadata = doc.get("metadata", {})
        namespace = metadata.get("namespace")
        if namespace not in webhook_namespaces:
            continue
        spec = doc.get("spec", {})
        if spec.get("podSelector") != {} or "Ingress" not in spec.get("policyTypes", []):
            continue
        from_rules = [
            source
            for rule in spec.get("ingress", [])
            for source in rule.get("from", [])
        ]
        source_namespaces = {
            source.get("namespaceSelector", {})
            .get("matchLabels", {})
            .get("kubernetes.io/metadata.name")
            for source in from_rules
        }
        if source_namespaces == {forbidden_source}:
            offending.append(
                f"{path.relative_to(obs_dir)}:{namespace}/{metadata.get('name')}"
            )

assert not offending, offending
PY
pass "observability NetworkPolicies do not isolate operator webhooks"

if [[ "$STATIC_ONLY" -eq 1 ]]; then
  skip "runtime observability proof skipped by --static-only"
  finish
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
command -v curl >/dev/null 2>&1 || die "curl is required for runtime proof"
[[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

if ! kubectl_cmd get namespace observability-system >/dev/null 2>&1; then
  skip "runtime proof skipped; observability-system namespace is not installed"
  finish
  exit 0
fi

kubectl_cmd -n observability-system rollout status deployment/prometheus --timeout=300s >/dev/null
kubectl_cmd -n observability-system rollout status deployment/grafana --timeout=300s >/dev/null
kubectl_cmd -n observability-system rollout status deployment/alertmanager --timeout=300s >/dev/null
kubectl_cmd -n observability-system rollout status deployment/loki --timeout=300s >/dev/null
kubectl_cmd -n observability-system rollout status daemonset/otel-collector --timeout=300s >/dev/null
pass "observability Pods are Ready"

start_port_forward() {
  local service="$1"
  local local_port="$2"
  local remote_port="$3"
  local log_file="${TMP_DIR}/${service}-pf.log"
  kubectl_cmd -n observability-system port-forward "service/${service}" "${local_port}:${remote_port}" >"$log_file" 2>&1 &
  local pid="$!"
  PORT_FORWARD_PIDS+=("$pid")

  for _ in $(seq 1 30); do
    if grep -q 'Forwarding from' "$log_file"; then
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      cat "$log_file" >&2 || true
      die "port-forward for ${service} exited before becoming ready"
    fi
    sleep 1
  done

  cat "$log_file" >&2 || true
  die "port-forward for ${service} did not become ready"
}

start_port_forward prometheus 19090 9090
targets_endpoint="$(python3 - "$OBS_CONTRACT" <<'PY'
import sys
import yaml
print(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["prometheus_target_query"]["endpoint"])
PY
)"
targets_json="$(curl -fsS "http://127.0.0.1:19090${targets_endpoint}")"
jq -e '.status == "success" and (.data.activeTargets | length > 0)' <<<"$targets_json" >/dev/null || die "Prometheus has active targets"
jq -e 'all(.data.activeTargets[]; .health == "up")' <<<"$targets_json" >/dev/null || die "Prometheus targets are all up"
echo "PROMETHEUS_TARGETS:"
jq -r '.data.activeTargets[] | "\(.labels.job) \(.health) \(.scrapeUrl)"' <<<"$targets_json" | sort
pass "Prometheus targets are all up"

start_port_forward grafana 13000 3000
grafana_health="$(curl -fsS http://127.0.0.1:13000/api/health)"
jq -e '.database == "ok"' <<<"$grafana_health" >/dev/null || die "Grafana health endpoint is ok"
dashboard_files="$(python3 - "$OBS_CONTRACT" <<'PY'
import json
import sys
import yaml
print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["dashboard_provisioning"]["required_files"]))
PY
)"
kubectl_cmd -n observability-system get configmap grafana-dashboards -o json \
  | jq -e --argjson files "$dashboard_files" '.data as $data | all($files[]; . as $file | $data | has($file))' >/dev/null \
  || die "Grafana dashboards ConfigMap is present"
pass "Grafana dashboard renders from provisioned ConfigMap"

start_port_forward alertmanager 19093 9093
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sample_alert_payload="$(python3 - "$OBS_CONTRACT" "$now" <<'PY'
import json
import sys
import yaml

contract = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
sample = contract["sample_alert"]
payload = [{
    "labels": {"alertname": sample["alertname"], **sample["labels"]},
    "annotations": sample["annotations"],
    "startsAt": sys.argv[2],
}]
print(json.dumps(payload))
PY
)"
curl -fsS -X POST -H 'Content-Type: application/json' \
  --data "$sample_alert_payload" \
  http://127.0.0.1:19093/api/v2/alerts >"${TMP_DIR}/alertmanager-post.out" 2>"${TMP_DIR}/alertmanager-post.err" \
  || die "failed to POST sample alert to Alertmanager: $(cat "${TMP_DIR}/alertmanager-post.err")"
sample_alert_name="$(python3 - "$OBS_CONTRACT" <<'PY'
import sys
import yaml
print(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["sample_alert"]["alertname"])
PY
)"
curl -fsS http://127.0.0.1:19093/api/v2/alerts \
  | jq -e --arg alertname "$sample_alert_name" 'any(.[]; .labels.alertname == $alertname and .labels.tenant == "platform")' >/dev/null \
  || die "sample alert fired through Alertmanager"
pass "sample alert fired through Alertmanager"

start_port_forward loki 13100 3100
ts="$(date +%s)000000000"
sample_log_payload="$(python3 - "$OBS_CONTRACT" "$ts" <<'PY'
import json
import sys
import yaml

contract = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
sample = contract["sample_log"]
payload = {
    "streams": [{
        "stream": sample["stream"],
        "values": [[sys.argv[2], sample["message"]]],
    }]
}
print(json.dumps(payload))
PY
)"
sample_log_query="$(python3 - "$OBS_CONTRACT" <<'PY'
import sys
import yaml
print(yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["sample_log"]["query"])
PY
)"
curl -fsS -X POST -H 'Content-Type: application/json' \
  --data "$sample_log_payload" \
  http://127.0.0.1:13100/loki/api/v1/push >"${TMP_DIR}/loki-push.out" 2>"${TMP_DIR}/loki-push.err" \
  || die "failed to push sample log to Loki: $(cat "${TMP_DIR}/loki-push.err")"
log_found=0
for _ in $(seq 1 10); do
  sleep 2
  if curl -fsS --get --data-urlencode "query=${sample_log_query}" \
    http://127.0.0.1:13100/loki/api/v1/query \
    | jq -e '.data.result | length > 0' >/dev/null; then
    log_found=1
    break
  fi
done
[[ "$log_found" -eq 1 ]] || die "sample log appears in Loki"
pass "sample log appears in Loki"

finish
