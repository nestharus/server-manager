#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"
KONG_NAMESPACE="kong-system"
KONG_DEPLOYMENT="kong-kong"
KONG_ADMIN_PORT="8444"
LOCAL_PORT="18444"
CLUSTER_MODE=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
PORT_FORWARD_PID=""
PORT_FORWARD_LOG=""
ROUTES_JSON="[]"

PUBLIC_INTAKE_TUPLES=(
  "api.local.humility.local|/api/v1/public/applications"
  "api.local.humility.local|/api/v1/public/chapters"
  "web.local.humility.local|/api/public/applications"
  "web.local.humility.local|/api/public/chapters"
  "web.local.humility.local|/api/applications"
)

REQUIRED_NEGATIVE_HOST="api.local.humility.local"
REQUIRED_NEGATIVE_PATH="/api/v1/web/admin/chapters"

usage() {
  cat <<'EOF'
Usage: validate_kong_kic_translation_local.sh [--cluster] [--kubeconfig PATH]

Validates Kong KIC runtime translation for public-intake rate limiting:
  - reaches Kong Admin API through a local HTTPS port-forward
  - walks Kong Routes with pagination
  - proves the five public-intake routes have enabled route-scoped rate-limiting
  - proves the adjacent authenticated admin path does not have route-scoped rate-limiting

Options:
  --cluster          Run explicit cluster runtime validation
  --kubeconfig PATH  Kubeconfig for the local k3d channel
  -h, --help         Show this help
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
  if [[ -n "${PORT_FORWARD_PID:-}" ]] && kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
    kill "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
    wait "$PORT_FORWARD_PID" >/dev/null 2>&1 || true
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cluster)
        CLUSTER_MODE=1
        ;;
      --kubeconfig)
        [[ $# -ge 2 ]] || die "--kubeconfig requires a value"
        KUBECONFIG_PATH="$2"
        shift 2
        continue
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

require_tools() {
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
  command -v curl >/dev/null 2>&1 || die "curl is required"
  command -v jq >/dev/null 2>&1 || die "jq is required"
}

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

start_port_forward() {
  mkdir -p "${REPO_ROOT}/.tmp"
  PORT_FORWARD_LOG="${REPO_ROOT}/.tmp/kong-kic-admin-port-forward.log"
  : >"$PORT_FORWARD_LOG"

  kubectl_cmd -n "$KONG_NAMESPACE" port-forward deploy/kong-kong "${LOCAL_PORT}:${KONG_ADMIN_PORT}" >"$PORT_FORWARD_LOG" 2>&1 &
  PORT_FORWARD_PID="$!"
  trap cleanup EXIT INT TERM
}

admin_api_url() {
  local endpoint="$1"

  if [[ "$endpoint" == http://* || "$endpoint" == https://* ]]; then
    printf '%s\n' "$endpoint"
    return
  fi

  if [[ "$endpoint" != /* ]]; then
    endpoint="/${endpoint}"
  fi
  printf 'https://127.0.0.1:%s%s\n' "$LOCAL_PORT" "$endpoint"
}

admin_api() {
  local endpoint="$1"
  local url

  url="$(admin_api_url "$endpoint")"
  curl --fail --silent --show-error --insecure "$url"
}

wait_admin_api() {
  local attempt

  for attempt in $(seq 1 60); do
    if admin_api "/status" >/dev/null 2>&1; then
      pass "Kong Admin API reachable through localhost:${LOCAL_PORT}"
      return
    fi
    if ! kill -0 "$PORT_FORWARD_PID" >/dev/null 2>&1; then
      die "kubectl port-forward exited early; see ${PORT_FORWARD_LOG}"
    fi
    sleep 1
  done

  die "Kong Admin API did not become reachable on localhost:${LOCAL_PORT}; see ${PORT_FORWARD_LOG}"
}

walk_routes() {
  local endpoint="/routes"
  local page
  local next

  ROUTES_JSON="[]"
  while [[ -n "$endpoint" && "$endpoint" != "null" ]]; do
    page="$(admin_api "$endpoint")"
    ROUTES_JSON="$(jq -c --argjson page "$page" '. + ($page.data // [])' <<<"$ROUTES_JSON")"
    next="$(jq -r '.next // empty' <<<"$page")"
    endpoint="$next"
  done

  if [[ "$(jq -r 'length' <<<"$ROUTES_JSON")" -eq 0 ]]; then
    emit_routes_diagnostic ""
    die "precondition failed: empty Kong Route table; expected at least one Kong Route; got zero - likely GitOps not reconciled"
  fi

  pass "discovered Kong Routes through paginated /routes"
}

walk_route_plugins() {
  local route_id="$1"
  local endpoint="/routes/${route_id}/plugins"
  local page
  local next
  local plugins_json="[]"

  while [[ -n "$endpoint" && "$endpoint" != "null" ]]; do
    page="$(admin_api "$endpoint")"
    plugins_json="$(jq -c --argjson page "$page" '. + ($page.data // [])' <<<"$plugins_json")"
    next="$(jq -r '.next // empty' <<<"$page")"
    endpoint="$next"
  done

  printf '%s\n' "$plugins_json"
}

emit_route_diagnostic_line() {
  local route_id="$1"
  local route_json
  local hosts
  local paths
  local plugins_json
  local plugin_names

  route_json="$(jq -c --arg id "$route_id" '.[] | select(.id == $id)' <<<"$ROUTES_JSON")"
  hosts="$(jq -r '(.hosts // []) | "[" + join(",") + "]"' <<<"$route_json")"
  paths="$(jq -r '(.paths // []) | "[" + join(",") + "]"' <<<"$route_json")"
  plugins_json="$(walk_route_plugins "$route_id")"
  plugin_names="$(jq -r '[.[] | .name] | "[" + join(",") + "]"' <<<"$plugins_json")"

  echo "ROUTE id=${route_id}|hosts=${hosts}|paths=${paths}|plugins=${plugin_names}" >&2
}

emit_routes_diagnostic() {
  local host="$1"
  local route_ids
  local route_id

  route_ids="$(jq -r --arg host "$host" '.[] | select($host == "" or ((.hosts // []) | index($host))) | .id' <<<"$ROUTES_JSON")"
  if [[ -z "$route_ids" ]]; then
    echo "ROUTE id=<none>|hosts=[${host}]|paths=[]|plugins=[]" >&2
    return
  fi

  while IFS= read -r route_id; do
    [[ -n "$route_id" ]] || continue
    emit_route_diagnostic_line "$route_id"
  done <<<"$route_ids"
}

resolve_exact_route_id() {
  local host="$1"
  local path="$2"
  local ids_json
  local count

  ids_json="$(
    jq -c --arg host "$host" --arg path "$path" '
      def matches_expected_path($expected):
        . == $expected
        or . == ($expected + "/")
        or . == ("~" + $expected + "$")
        or . == ("~^" + $expected + "$");

      [
        .[]
        | select((.hosts // []) | index($host))
        | select(any((.paths // [])[]; matches_expected_path($path)))
        | .id
      ]
    ' <<<"$ROUTES_JSON"
  )"
  count="$(jq -r 'length' <<<"$ids_json")"

  if [[ "$count" -ne 1 ]]; then
    emit_routes_diagnostic "$host"
    die "expected exactly one Kong Route for ${host}${path}; got ${count}"
  fi

  jq -r '.[0]' <<<"$ids_json"
}

resolve_handling_route_id() {
  local host="$1"
  local request_path="$2"
  local candidates_json
  local count

  candidates_json="$(
    jq -c --arg host "$host" --arg request_path "$request_path" '
      def normalize_route_path:
        sub("^~"; "") | sub("^\\^"; "") | sub("\\$$"; "");
      def handles_request($request):
        normalize_route_path as $route_path
        | ($route_path == "/")
          or ($request == $route_path)
          or ($request | startswith($route_path + "/"));

      [
        .[]
        | select((.hosts // []) | index($host))
        | . as $route
        | [($route.paths // [])[] | select(handles_request($request_path)) | normalize_route_path] as $matched_paths
        | select(($matched_paths | length) > 0)
        | {id: $route.id, score: ($matched_paths | map(length) | max)}
      ] as $matches
      | if ($matches | length) == 0 then []
        else ($matches | map(.score) | max) as $best | $matches | map(select(.score == $best))
        end
    ' <<<"$ROUTES_JSON"
  )"
  count="$(jq -r 'length' <<<"$candidates_json")"

  if [[ "$count" -ne 1 ]]; then
    emit_routes_diagnostic "$host"
    die "expected exactly one Kong Route handling ${host}${request_path}; got ${count}"
  fi

  jq -r '.[0].id' <<<"$candidates_json"
}

assert_route_has_rate_limiting() {
  local route_id="$1"
  local host="$2"
  local path="$3"
  local plugins_json

  plugins_json="$(walk_route_plugins "$route_id")"
  if jq -e '[.[] | select((.enabled == true) and (.name == "rate-limiting"))] | length > 0' <<<"$plugins_json" >/dev/null; then
    pass "enabled route-scoped rate-limiting plugin present for ${host}${path}"
    return
  fi

  emit_route_diagnostic_line "$route_id"
  die "missing enabled route-scoped rate-limiting plugin for ${host}${path}"
}

assert_route_lacks_rate_limiting() {
  local route_id="$1"
  local host="$2"
  local path="$3"
  local plugins_json

  plugins_json="$(walk_route_plugins "$route_id")"
  if jq -e '[.[] | select((.enabled == true) and (.name == "rate-limiting"))] | length == 0' <<<"$plugins_json" >/dev/null; then
    pass "no enabled route-scoped rate-limiting plugin present for ${host}${path}"
    return
  fi

  emit_route_diagnostic_line "$route_id"
  die "unexpected enabled route-scoped rate-limiting plugin for ${host}${path}"
}

assert_public_intake_routes() {
  local tuple
  local host
  local path
  local route_id

  for tuple in "${PUBLIC_INTAKE_TUPLES[@]}"; do
    IFS='|' read -r host path <<<"$tuple"
    route_id="$(resolve_exact_route_id "$host" "$path")"
    pass "resolved Kong Route for ${host}${path}"
    assert_route_has_rate_limiting "$route_id" "$host" "$path"
  done
}

assert_required_negative() {
  local route_id

  route_id="$(resolve_handling_route_id "$REQUIRED_NEGATIVE_HOST" "$REQUIRED_NEGATIVE_PATH")"
  pass "resolved Kong Route handling ${REQUIRED_NEGATIVE_HOST}${REQUIRED_NEGATIVE_PATH}"
  assert_route_lacks_rate_limiting "$route_id" "$REQUIRED_NEGATIVE_HOST" "$REQUIRED_NEGATIVE_PATH"
}

main() {
  parse_args "$@"
  require_tools

  if [[ "$CLUSTER_MODE" -eq 1 ]]; then
    pass "cluster runtime mode requested"
  fi

  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  start_port_forward
  wait_admin_api
  walk_routes
  assert_public_intake_routes
  assert_required_negative
  finish
}

main "$@"
