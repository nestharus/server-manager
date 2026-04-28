#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESOLVER="${REPO_ROOT}/infra/scripts/resolve_platform_channel.py"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
STATIC_ONLY=0
KEEP=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TEMP_FILES=()

AUTH_NAMESPACE="auth-system"
AUTHENTIK_HOST="auth.local.humility.local"
POMERIUM_HOST="protected-api.local.humility.local"
PROTECTED_PATH="/api/v1/protected/authz-proof"

usage() {
  cat <<'EOF'
Usage: validate_auth_stack_local.sh [--channel local] [--kubeconfig PATH] [--static-only] [--keep]

Validates INIT-114 local auth stack:
  - channel auth_stack schema resolution
  - Helm render reproducibility for Authentik, Pomerium, and OPAL/Cedar
  - local auth kustomize and root inclusion
  - optional runtime proof for Authentik, Pomerium, Cedar, and protected API auth challenge
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
  local temp_file
  for temp_file in "${TEMP_FILES[@]:-}"; do
    rm -f "$temp_file" >/dev/null 2>&1 || true
  done
  if [[ "$KEEP" -eq 0 && -f "$KUBECONFIG_PATH" ]] && command -v kubectl >/dev/null 2>&1; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$AUTH_NAMESPACE" delete pod init-114-cedar init-114-protected-api --ignore-not-found >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
        shift 2
        continue
        ;;
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift 2
        continue
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

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

assert_file() {
  local path="$1"
  [[ -f "${REPO_ROOT}/${path}" ]] && pass "exists: ${path}" || die "missing: ${path}"
}

assert_channel_contract() {
  local resolved
  resolved="$("$PYTHON_BIN" "$RESOLVER" --channel "$CHANNEL_REQUEST")"

  jq -e '.auth_stack.namespace == "auth-system"' <<<"$resolved" >/dev/null || die "auth namespace contract"
  jq -e '.auth_stack.authentik.chart_version == "2026.2.2"' <<<"$resolved" >/dev/null || die "Authentik chart contract"
  jq -e '.auth_stack.pomerium.chart_version == "34.0.1"' <<<"$resolved" >/dev/null || die "Pomerium chart contract"
  jq -e '.auth_stack.opal_cedar.client_image == "docker.io/permitio/opal-client-cedar:0.7.12"' <<<"$resolved" >/dev/null || die "OPAL Cedar client contract"
  jq -e '.auth_stack.protected_api.proof_path == "/api/v1/protected/authz-proof"' <<<"$resolved" >/dev/null || die "protected API proof path contract"
  pass "resolved channel auth_stack contract"
}

assert_static_files() {
  assert_file "gitops/channels/local/auth/kustomization.yaml"
  assert_file "gitops/channels/local/auth/authentik/render-values.yaml"
  assert_file "gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml"
  assert_file "gitops/channels/local/auth/pomerium/render-values.yaml"
  assert_file "gitops/channels/local/auth/pomerium/rendered/pomerium-34.0.1.yaml"
  assert_file "gitops/channels/local/auth/opal-cedar/render-values.yaml"
  assert_file "gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml"
}

assert_helm_render_reproducible() {
  local rendered
  command -v helm >/dev/null 2>&1 || die "helm is required"

  ensure_helm_repo "authentik" "https://charts.goauthentik.io"
  ensure_helm_repo "pomerium" "https://helm.pomerium.io"
  ensure_helm_repo "permitio" "https://permitio.github.io/opal-helm-chart"

  rendered="$(mktemp)"
  TEMP_FILES+=("$rendered")
  helm template authentik authentik/authentik --version 2026.2.2 --namespace auth-system \
    -f "${REPO_ROOT}/gitops/channels/local/auth/authentik/render-values.yaml" >"$rendered"
  diff -u "${REPO_ROOT}/gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml" "$rendered" \
    || die "Authentik Helm render is not reproducible"
  pass "Authentik Helm render is reproducible"

  rendered="$(mktemp)"
  TEMP_FILES+=("$rendered")
  helm template pomerium pomerium/pomerium --version 34.0.1 --namespace auth-system \
    -f "${REPO_ROOT}/gitops/channels/local/auth/pomerium/render-values.yaml" >"$rendered"
  diff -u "${REPO_ROOT}/gitops/channels/local/auth/pomerium/rendered/pomerium-34.0.1.yaml" "$rendered" \
    || die "Pomerium Helm render is not reproducible"
  pass "Pomerium Helm render is reproducible"

  rendered="$(mktemp)"
  TEMP_FILES+=("$rendered")
  helm template opal permitio/opal --version 0.0.29 --namespace auth-system \
    -f "${REPO_ROOT}/gitops/channels/local/auth/opal-cedar/render-values.yaml" >"$rendered"
  diff -u "${REPO_ROOT}/gitops/channels/local/auth/opal-cedar/rendered/opal-0.0.29.yaml" "$rendered" \
    || die "OPAL/Cedar Helm render is not reproducible"
  pass "OPAL/Cedar Helm render is reproducible"
}

assert_kustomize() {
  local auth_render
  local local_render
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"

  auth_render="$(mktemp)"
  local_render="$(mktemp)"
  TEMP_FILES+=("$auth_render" "$local_render")

  kubectl kustomize "${REPO_ROOT}/gitops/channels/local/auth" >"$auth_render"
  pass "auth stack kustomize"

  kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >"$local_render"
  pass "local root kustomization includes auth"

  grep -q 'name: authentik-postgres' "$auth_render" || die "Authentik CNPG Cluster rendered"
  grep -q 'host: auth.local.humility.local' "$auth_render" || die "Authentik ingress rendered"
  grep -q 'host: protected-api.local.humility.local' "$auth_render" || die "protected API ingress rendered"
  grep -q 'permitio/opal-client-cedar:0.7.12' "$auth_render" || die "Cedar OPAL client image rendered"
  grep -q 'CEDAR_AUTHORIZATION_URL' "$local_render" || die "API Cedar authorization env rendered"
  python3 - <<PY || die "legacy Cedar direct writer resources rendered"
import yaml
from pathlib import Path
for doc in yaml.safe_load_all(Path("$auth_render").read_text()):
    if not isinstance(doc, dict):
        continue
    kind = doc.get("kind")
    name = doc.get("metadata", {}).get("name")
    if (kind, name) in {
        ("Job", "cedar-access-policy-" + "bootstrap"),
        ("ConfigMap", "cedar-access-policy-" + "bundle"),
    }:
        raise SystemExit(1)
PY
  pass "auth stack resources rendered"
}

assert_no_secret_literals() {
  local secret_matches
  secret_matches="$(mktemp)"
  TEMP_FILES+=("$secret_matches")

  if rg -n '(AUTHENTIK_BOOTSTRAP_PASSWORD|AUTHENTIK_SECRET_KEY|OIDC_CLIENT_SECRET|COOKIE_SECRET|SHARED_SECRET|SIGNING_KEY):[[:space:]]+[^"{[:space:]]' \
    "${REPO_ROOT}/gitops/channels/local/auth" >"$secret_matches"; then
    cat "$secret_matches" >&2
    die "no committed auth credential literals"
  fi
  pass "no committed auth credential literals"
}

ensure_helm_repo() {
  local name="$1"
  local url="$2"

  if ! helm repo list -o yaml | grep -Eq "^[[:space:]-]*name: ${name}$"; then
    helm repo add "$name" "$url" >/dev/null
  fi
}

assert_runtime() {
  local allowed_body
  local denied_body
  local expected_policy_ids
  local status

  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime proof skipped by --static-only"
    return
  fi
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  kubectl_cmd -n "$AUTH_NAMESPACE" wait cluster/authentik-postgres --for=condition=Ready --timeout=300s >/dev/null
  pass "Authentik CNPG Cluster Ready=True"

  kubectl_cmd -n "$AUTH_NAMESPACE" rollout status deployment/authentik-server --timeout=300s >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" rollout status deployment/authentik-worker --timeout=300s >/dev/null
  pass "Authentik server and worker available"

  kubectl_cmd -n "$AUTH_NAMESPACE" rollout status deployment/pomerium-proxy --timeout=300s >/dev/null
  pass "Pomerium all-in-one proxy available"

  kubectl_cmd -n "$AUTH_NAMESPACE" rollout status deployment/opal-client --timeout=300s >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" rollout status deployment/opal-server --timeout=300s >/dev/null
  # OPAL Cedar uploader uses the policy file's full repo-relative path as the
  # Cedar policy ID — see validate_access_policy_local.sh::expected_policy_ids_json.
  local generated_rel="policy/cedar/channels/local/services/server-manager-api/generated/policies"
  expected_policy_ids="$(jq -c --arg p "$generated_rel" '[.[].id | "\($p)/\(.).cedar"] | sort' "${REPO_ROOT}/policy/cedar/channels/local/services/server-manager-api/policies.json")"
  pass "OPAL/Cedar deployments available"

  kubectl_cmd -n "$AUTH_NAMESPACE" delete pod init-114-cedar --ignore-not-found >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" run init-114-cedar \
    --restart=Never \
    --labels=app.kubernetes.io/name=opal-cedar,platform.humility.gg/init=114 \
    --image=curlimages/curl:8.16.0 \
    --env="EXPECTED_POLICY_IDS=${expected_policy_ids}" \
    --command -- /bin/sh -ec "expected=\$(printf '%s' \"\$EXPECTED_POLICY_IDS\" | tr -d '[]\"' | tr ',' ' '); missing=\"\$expected\"; for attempt in \$(seq 1 120); do body=\$(curl -fsS http://opal-client:8180/v1/policies 2>/dev/null || true); missing=''; if [ -n \"\$body\" ]; then for id in \$expected; do if ! printf '%s' \"\$body\" | grep -Eq '\"id\"[[:space:]]*:[[:space:]]*\"'\"\$id\"'\"'; then missing=\"\$missing \$id\"; fi; done; [ -z \"\$missing\" ] && break; fi; sleep 1; done; [ -z \"\$missing\" ] || { printf 'missing policy IDs:%s\nlast policies: %s\n' \"\$missing\" \"\$body\" >&2; exit 1; }; curl -fsS -X POST -H 'Content-Type: application/json' --data '{\"principal\":\"User::\\\"sample@local.humility.local\\\"\",\"action\":\"Action::\\\"api:read\\\"\",\"resource\":\"Resource::\\\"server-manager-api\\\"\"}' http://opal-client:8180/v1/is_authorized && echo && curl -fsS -X POST -H 'Content-Type: application/json' --data '{\"principal\":\"User::\\\"other@local.humility.local\\\"\",\"action\":\"Action::\\\"api:read\\\"\",\"resource\":\"Resource::\\\"server-manager-api\\\"\"}' http://opal-client:8180/v1/is_authorized" >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" wait pod/init-114-cedar --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null
  allowed_body="$(kubectl_cmd -n "$AUTH_NAMESPACE" logs pod/init-114-cedar | sed -n '1p')"
  denied_body="$(kubectl_cmd -n "$AUTH_NAMESPACE" logs pod/init-114-cedar | sed -n '2p')"
  grep -q '"decision":"Allow"' <<<"$allowed_body" || die "Cedar allowed sample user"
  grep -q '"decision":"Deny"' <<<"$denied_body" || die "Cedar denied non-sample user"
  pass "Cedar policy enforces sample user rule"

  kubectl_cmd -n "$AUTH_NAMESPACE" delete pod init-114-protected-api --ignore-not-found >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" run init-114-protected-api \
    --restart=Never \
    --labels=app.kubernetes.io/name=auth-stack-probe,platform.humility.gg/init=114 \
    --image=curlimages/curl:8.16.0 \
    --command -- /bin/sh -ec "code=\$(curl -ksS -H 'Host: ${POMERIUM_HOST}' -o /dev/null -w '%{http_code}' https://kong-kong-proxy.kong-system.svc.cluster.local${PROTECTED_PATH}); test \"\$code\" = 302 -o \"\$code\" = 401 -o \"\$code\" = 403" >/dev/null
  kubectl_cmd -n "$AUTH_NAMESPACE" wait pod/init-114-protected-api --for=jsonpath='{.status.phase}'=Succeeded --timeout=180s >/dev/null
  status="$(kubectl_cmd -n "$AUTH_NAMESPACE" logs pod/init-114-protected-api || true)"
  [[ -z "$status" ]] || die "protected API probe emitted unexpected output: ${status}"
  pass "protected API requires authentication through Pomerium"

  kubectl_cmd -n "$AUTH_NAMESPACE" get secret authentik-config -o jsonpath='{.data.AUTHENTIK_BOOTSTRAP_PASSWORD}' | grep -q .
  kubectl_cmd -n "$AUTH_NAMESPACE" get secret authentik-config -o jsonpath='{.data.SAMPLE_USER_PASSWORD}' | grep -q .
  pass "Authentik admin and sample user credentials synced from Infisical"
}

main() {
  parse_args "$@"
  PYTHON_BIN="$(python_bin)" || die "python or python3 is required"
  command -v jq >/dev/null 2>&1 || die "jq is required"
  command -v rg >/dev/null 2>&1 || die "rg is required"

  assert_channel_contract
  assert_static_files
  assert_helm_render_reproducible
  assert_kustomize
  assert_no_secret_literals
  assert_runtime
  finish
}

main "$@"
