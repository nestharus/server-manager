#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
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

Validates INIT-118 web UI substrate:
  - Solid 2/Vite/TanStack/Ark/vanilla CSS package surface
  - FontAwesome npm token flow without committed token material
  - local GitOps SPA deployment and Pomerium-fronted routes
  - optional local runtime proof: image build, Pod Ready, public route 200, admin route auth redirect
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

assert_file() {
  local path="$1"
  [[ -f "${REPO_ROOT}/${path}" ]] && pass "exists: ${path}" || die "missing: ${path}"
}

assert_package_surface() {
  assert_file "services/web/package.json"
  assert_file "services/web/package-lock.json"
  assert_file "services/web/vite.config.ts"
  assert_file "services/web/.oxlintrc.json"
  assert_file "services/web/.oxfmt.json"
  assert_file "services/web/.npmrc.template"
  assert_file "services/web/src/styles/layers.css"
  assert_file "services/web/src/solid-compat/solid.ts"

  node -e '
const pkg = require("./services/web/package.json")
const deps = {...pkg.dependencies, ...pkg.devDependencies}
const expected = {
  "solid-js": "2.0.0-beta.8",
  "@solidjs/web": "2.0.0-beta.8",
  "vite-plugin-solid": "3.0.0-next.5",
  "@tanstack/solid-router": "1.168.25",
  "@tanstack/solid-query": "5.100.5",
  "@tanstack/solid-form": "1.29.1",
  "@ark-ui/solid": "5.36.2",
  "oxlint": "1.62.0",
  "oxfmt": "0.47.0",
  "@typescript/native-preview": "7.0.0-dev.20260427.1",
  "@playwright/test": "1.59.1"
}
for (const [name, version] of Object.entries(expected)) {
  if (deps[name] !== version) throw new Error(`${name} expected ${version}; got ${deps[name]}`)
}
' || die "web package pins match INIT-118 contract"
  pass "web package pins match INIT-118 contract"

  if rg -n 'tailwind|panda|styled-components|@emotion|webawesome' "${REPO_ROOT}/services/web/package.json" "${REPO_ROOT}/services/web/src" >/tmp/init118-forbidden.txt; then
    cat /tmp/init118-forbidden.txt >&2
    die "no forbidden styling/component packages"
  fi
  pass "no Tailwind, Panda, styling DSL, or WebAwesome primary dependency"

  if [[ -f "${REPO_ROOT}/services/web/.npmrc" ]] && rg -n '_authToken=.*[A-Za-z0-9_-]{12,}' "${REPO_ROOT}/services/web/.npmrc"; then
    die "no committed npm token material"
  fi
  pass "no committed npm token material"
}

assert_web_build() {
  (cd "${REPO_ROOT}/services/web" && npm run build >/tmp/init118-web-build.log)
  pass "web SPA builds with Solid 2 beta compatibility gate"
}

assert_kustomize() {
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required for kustomize validation"
  local render
  render="$(mktemp)"
  kubectl kustomize "${REPO_ROOT}/gitops/channels/local/applications/web" >"$render"
  grep -q 'name: server-manager-web' "$render" || die "web workload renders"
  grep -q "local/server-manager-web:${IMAGE_TAG}" "$render" || die "web image tag renders"
  pass "web application kustomize renders"

  kubectl kustomize --load-restrictor=LoadRestrictionsNone "${REPO_ROOT}/gitops/channels/local" >/tmp/init118-local-render.yaml
  grep -q 'host: web.local.humility.local' /tmp/init118-local-render.yaml || die "web Pomerium ingress renders"
  grep -q 'allow_public_unauthenticated_access: true' /tmp/init118-local-render.yaml || die "public Pomerium route renders"
  grep -q 'prefix: /admin' /tmp/init118-local-render.yaml || die "admin Pomerium route renders"
  pass "local root includes Pomerium-fronted web route"
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

  local public_code
  public_code="$(curl -k -o /dev/null -w "%{http_code}" https://web.local.humility.local/ || true)"
  [[ "$public_code" == "200" ]] || die "public route returned 200; got ${public_code}"
  pass "public route returned 200"

  local admin_code
  admin_code="$(curl -k -o /dev/null -w "%{http_code}" https://web.local.humility.local/admin/chapters || true)"
  [[ "$admin_code" =~ ^(302|303|401)$ ]] || die "admin route requires auth; got ${admin_code}"
  pass "admin route requires authentication"
}

main() {
  parse_args "$@"
  command -v rg >/dev/null 2>&1 || die "rg is required"
  assert_package_surface
  assert_web_build
  assert_kustomize
  assert_runtime
  finish
}

main "$@"
