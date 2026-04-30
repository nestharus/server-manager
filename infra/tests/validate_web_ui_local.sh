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
assert(contract.routes.officer_queue.path === "/applications/queue", "officer queue path")
assert(contract.routes.officer_queue.requires_auth === true, "officer queue requires auth")
assert(contract.routes.officer_detail.path === "/applications/{id}", "officer detail path")
assert(contract.routes.officer_detail.requires_auth === true, "officer detail requires auth")
assert(contract.routes.admin.requires_auth === true, "admin route requires auth")
assert(contract.auth.unauthenticated_api_status === 401, "unauthenticated_api_status")
assert(contract.auth.probe_endpoint === "/api/me", "principal probe endpoint")
assert(contract.auth.identity.groups.includes("officers"), "officer group fixture")
assert(contract.auth.identity.discord_user_id === "210987654321098765", "officer Discord claim fixture")
assert(contract.form.submit.method === "POST", "form submit method")
assert(contract.form.submit.endpoint === "/api/public/applications", "public form submit endpoint")
assert(contract.form.submit.success_status === 201, "form success status")
assert(contract.form.fields.map((field) => field.name).sort().join(",") === "application_text,character_name", "form fields")
assert(contract.form.submit.payload_fields.map((field) => field.name).sort().join(",") === "responses.application_text,responses.character_name,scope.scope_id,scope.scope_kind", "public submit payload fields")
assert(contract.form.submit.client_application_id_pattern.includes("-4"), "client_application_id UUIDv4 pattern")
assert(Object.keys(contract.ui_libraries).sort().join(",") === "ark,fontawesome,tanstack", "UI library coverage")
assert(contract.applications.queue.endpoint === "/api/web/officer/applications", "officer queue endpoint")
assert(contract.applications.queue.state_filter === "submitted,queued", "officer queue default state filter")
assert(contract.applications.claim.endpoint === "/api/web/officer/applications/{id}/claim", "officer claim endpoint")
assert(contract.applications.claim.if_match_header === true, "officer claim uses If-Match")
assert(contract.applications.detail.endpoint === "/api/web/officer/applications/{id}", "officer detail endpoint")
assert(contract.applications.detail.method === "GET", "officer detail method")
assert(contract.applications.transcript.endpoint === "/api/web/officer/applications/{id}/transcript", "officer transcript endpoint")
assert(contract.applications.transcript.method === "GET", "officer transcript method")
assert(contract.applications.message.endpoint === "/api/web/officer/applications/{id}/messages", "officer message endpoint")
assert(contract.applications.message.method === "POST", "officer message method")
assert(contract.applications.message.success_statuses.join(",") === "201,200", "officer message success statuses")
assert(contract.applications.message.visibility_values.join(",") === "applicant_visible,officer_only", "officer message visibility values")
assert(contract.applications.transition.endpoint === "/api/web/officer/applications/{id}/transitions", "officer transition endpoint")
assert(contract.applications.transition.method === "POST", "officer transition method")
assert(contract.applications.transition.if_match_header === true, "officer transition uses If-Match")
assert(contract.applications.transition.success_status === 200, "officer transition success status")
assert(contract.applications.transition.actions.includes("review"), "officer transition includes review")
assert(contract.applications.transition.actions.includes("approve"), "officer transition includes approve")
assert(contract.applications.transition.rejected_actions.includes("claim"), "officer transition rejects claim")
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

assert_officer_queue_contract_spec() {
  local spec="${REPO_ROOT}/services/web/tests/officer-queue.spec.ts"
  [[ -f "$spec" ]] || die "missing Playwright officer queue spec"
  rg -q 'contract\.json' "$spec" || die "officer queue spec reads fixture"
  rg -q 'state_filter' "$spec" || die "officer queue spec covers default state filter"
  rg -q 'if-match' "$spec" || die "officer queue spec covers If-Match claim"
  pass "Playwright spec covers officer queue and claim"
}

assert_officer_detail_contract_spec() {
  local spec="${REPO_ROOT}/services/web/tests/officer-detail.spec.ts"
  [[ -f "$spec" ]] || die "missing Playwright officer detail spec"
  rg -q 'contract\.json' "$spec" || die "officer detail spec reads fixture"
  rg -q 'officer_detail' "$spec" || die "officer detail spec covers route fixture"
  rg -q 'application-detail-state' "$spec" || die "officer detail spec covers state test id"
  rg -q 'application-detail-version' "$spec" || die "officer detail spec covers version test id"
  rg -q 'application-transcript' "$spec" || die "officer detail spec covers transcript test id"
  rg -q 'body_markdown' "$spec" || die "officer detail spec covers actual transcript message field"
  rg -q 'state_change' "$spec" || die "officer detail spec covers transcript state changes"
  pass "Playwright spec covers officer detail and transcript"
}

assert_officer_actions_contract_spec() {
  local spec="${REPO_ROOT}/services/web/tests/officer-actions.spec.ts"
  [[ -f "$spec" ]] || die "missing Playwright officer actions spec"
  rg -q 'contract\.json' "$spec" || die "officer actions spec reads fixture"
  rg -q 'application-message-composer' "$spec" || die "officer actions spec covers message composer test id"
  rg -q 'application-transition-action-' "$spec" || die "officer actions spec covers transition action test ids"
  rg -q 'client_message_id' "$spec" || die "officer actions spec covers message idempotency token"
  rg -q 'if-match' "$spec" || die "officer actions spec covers transition If-Match"
  rg -q 'author_actor_id.*toBeUndefined' "$spec" || die "officer actions spec blocks browser author fields"
  pass "Playwright spec covers officer message and transition actions"
}

assert_web_source_api_paths() {
  if grep -rE "[\"']/api/v1/" "${REPO_ROOT}/services/web/src/" >/tmp/web-api-v1-grep.log; then
    cat /tmp/web-api-v1-grep.log >&2
    die "web source must use browser-facing /api paths, not /api/v1 literals"
  fi

  local client="${REPO_ROOT}/services/web/src/api/client.ts"
  rg -q '"/api/me"' "$client" || die "client.ts calls /api/me"
  rg -q '"/api/web/admin/chapters"' "$client" || die "client.ts calls /api/web/admin/chapters"
  rg -q '/api/web/officer/applications' "$client" || die "client.ts calls /api/web/officer/applications"
  rg -q '/api/web/officer/applications/\$\{input\.applicationId\}/claim' "$client" || die "client.ts calls officer claim endpoint"
  rg -q '/api/web/officer/applications/\$\{applicationId\}`' "$client" || die "client.ts calls officer detail endpoint"
  rg -q '/api/web/officer/applications/\$\{applicationId\}/transcript' "$client" || die "client.ts calls officer transcript endpoint"
  rg -q '/api/web/officer/applications/\$\{input\.applicationId\}/messages' "$client" || die "client.ts calls officer message endpoint"
  rg -q '/api/web/officer/applications/\$\{input\.applicationId\}/transitions' "$client" || die "client.ts calls officer transition endpoint"
  rg -q '"/auth/discord/me"' "$client" || die "client.ts calls /auth/discord/me"
  pass "web source uses browser-facing API path allowlist"
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

  # /api/me identity-header round-trip is exercised by the Playwright
  # e2e through a real Pomerium-authenticated session in 19-web-ui;
  # static curl with simulated headers does not work because Pomerium
  # strips/overrides client-supplied x-pomerium-claim-* headers as a
  # security boundary.
}

main() {
  parse_args "$@"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  command -v node >/dev/null 2>&1 || die "node is required"
  assert_contract_fixture
  assert_playwright_contract_spec
  assert_officer_queue_contract_spec
  assert_officer_detail_contract_spec
  assert_officer_actions_contract_spec
  assert_web_source_api_paths
  assert_web_build
  assert_runtime
  finish
}

main "$@"
