#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONTRACT_FIXTURE="${REPO_ROOT}/infra/tests/fixtures/web-ui/contract.json"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
IMAGE_TAG="init-118-local"
STATIC_ONLY=0
SKIP_IMAGE_BUILD=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

usage() {
  cat <<'EOF'
Usage: validate_web_ui_local.sh [--kubeconfig PATH] [--tag TAG] [--static-only] [--skip-image-build]

Validates SLICE-R.22 web UI behavior:
  - fixture-derived public route, authenticated admin route, API auth gate, and public form submit contract
  - Playwright spec coverage for route, auth, submit, Ark, FontAwesome, and TanStack behavior
  - optional local runtime proof: image build, Pod Ready, public route 200, admin route auth response
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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift 2
        continue
        ;;
      --tag)
        [[ $# -ge 2 ]] || die "--tag requires a value"
        IMAGE_TAG="$2"
        shift 2
        continue
        ;;
      --static-only)
        STATIC_ONLY=1
        ;;
      --skip-image-build)
        SKIP_IMAGE_BUILD=1
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

json_value() {
  local expr="$1"
  node -e '
const fs = require("fs")
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"))
const parts = process.argv[2].split(".")
let value = data
for (const part of parts) value = value[part]
if (Array.isArray(value) || typeof value === "object") {
  console.log(JSON.stringify(value))
} else {
  console.log(String(value))
}
' "$CONTRACT_FIXTURE" "$expr"
}

assert_contract_fixture() {
  [[ -f "$CONTRACT_FIXTURE" ]] || die "missing web UI contract fixture"
  node -e '
const fs = require("fs")
const contract = JSON.parse(fs.readFileSync(process.argv[1], "utf8"))
function assert(condition, message) {
  if (!condition) throw new Error(message)
}
assert(contract.routes.public.path === "/", "public route path")
assert(contract.routes.admin.requires_auth === true, "admin route requires auth")
assert(contract.auth.unauthenticated_api_status === 401, "unauthenticated_api_status")
assert(contract.form.submit.method === "POST", "form submit method")
assert(contract.form.submit.endpoint === "/api/public/applications", "public form submit endpoint")
assert(contract.form.submit.success_status === 201, "form success status")
assert(contract.form.fields.map((field) => field.name).sort().join(",") === "application_text,character_name", "form fields")
assert(contract.form.submit.payload_fields.map((field) => field.name).sort().join(",") === "responses.application_text,responses.character_name,scope.scope_id,scope.scope_kind", "public submit payload fields")
assert(contract.form.submit.client_application_id_pattern.includes("-4"), "client_application_id UUIDv4 pattern")
assert(Object.keys(contract.ui_libraries).sort().join(",") === "ark,fontawesome,tanstack", "UI library coverage")
' "$CONTRACT_FIXTURE" || die "web UI contract fixture is valid"
  pass "web UI contract fixture is valid"
}

assert_playwright_contract_spec() {
  local spec="${REPO_ROOT}/services/web/tests/compat.spec.ts"
  [[ -f "$spec" ]] || die "missing Playwright web UI contract spec"
  rg -q 'contract\.json' "$spec" || die "Playwright spec reads fixture"
  rg -q 'page\.route' "$spec" || die "Playwright spec stubs API routes"
  rg -q 'unauthenticated_api_status' "$spec" || die "Playwright spec covers auth-gated API behavior"
  rg -q 'success_status' "$spec" || die "Playwright spec covers form submit response"
  rg -q '/api/public/applications' "$CONTRACT_FIXTURE" || die "fixture targets public submit route"
  rg -q 'client_application_id_pattern' "$spec" || die "Playwright spec covers public client id contract"
  rg -q 'ui_libraries' "$spec" || die "Playwright spec covers UI library integration"
  if rg -q 'Dark Nemesis application|2\.0\.0-beta' "$spec"; then
    die "Playwright spec must not assert captured demo text or package versions"
  fi
  pass "Playwright spec covers route, auth, submit, and UI libraries"
}

assert_web_build() {
  if [[ ! -f "${REPO_ROOT}/services/web/package.json" ]]; then
    skip "web package is unavailable in this checkout"
    return
  fi
  (cd "${REPO_ROOT}/services/web" && npm run build >/tmp/slice-r22-web-build.log)
  pass "web SPA builds for local static contract"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

assert_runtime() {
  if [[ "$STATIC_ONLY" -eq 1 ]]; then
    skip "runtime proof skipped by --static-only"
    return
  fi
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for runtime proof"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  if [[ "$SKIP_IMAGE_BUILD" -eq 1 ]]; then
    skip "web image build skipped by --skip-image-build"
  else
    "${REPO_ROOT}/infra/scripts/build-channel-image.sh" \
      --channel local \
      --app server-manager-web \
      --tag "$IMAGE_TAG" \
      --context "$REPO_ROOT" \
      --file "${REPO_ROOT}/containers/server-manager/Containerfile.web"
    pass "web image built and pushed"
  fi

  kubectl_cmd -n web rollout status deployment/server-manager-web --timeout=300s >/dev/null
  pass "web Deployment Available"

  local public_host admin_host host_port host_loopback port_suffix
  public_host="$(json_value routes.public.host)"
  admin_host="$(json_value routes.admin.host)"
  host_port="$(json_value host_https_port)"
  host_loopback="$(json_value host_loopback)"
  port_suffix=""
  local resolve_args=()
  if [[ -n "$host_port" && -n "$host_loopback" ]]; then
    resolve_args+=(--resolve "${public_host}:${host_port}:${host_loopback}")
    [[ "$admin_host" != "$public_host" ]] && resolve_args+=(--resolve "${admin_host}:${host_port}:${host_loopback}")
    [[ "$host_port" != "443" ]] && port_suffix=":${host_port}"
  fi

  local public_url public_expected public_code
  public_url="https://${public_host}${port_suffix}$(json_value routes.public.path)"
  public_expected="$(json_value routes.public.status)"
  public_code="$(curl -k "${resolve_args[@]}" -o /dev/null -w "%{http_code}" "$public_url" || true)"
  [[ "$public_code" != "000" ]] || die "public route was unreachable; got curl 000"
  [[ "$public_code" == "$public_expected" ]] || die "public route returned ${public_expected}; got ${public_code}"
  pass "public route returned ${public_expected}"

  local admin_url admin_code allowed
  admin_url="https://${admin_host}${port_suffix}$(json_value routes.admin.path)"
  admin_code="$(curl -k "${resolve_args[@]}" -o /dev/null -w "%{http_code}" "$admin_url" || true)"
  [[ "$admin_code" != "000" ]] || die "admin route was unreachable; got curl 000"
  allowed="$(json_value routes.admin.allowed_unauthenticated_statuses)"
  node -e '
const allowed = JSON.parse(process.argv[1])
const code = Number(process.argv[2])
if (!allowed.includes(code)) process.exit(1)
' "$allowed" "$admin_code" || die "admin route requires auth; got ${admin_code}"
  pass "admin route requires authentication"
}

main() {
  parse_args "$@"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  command -v node >/dev/null 2>&1 || die "node is required"
  assert_contract_fixture
  assert_playwright_contract_spec
  assert_web_build
  assert_runtime
  finish
}

main "$@"
