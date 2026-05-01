#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHANNEL_REQUEST="local"
KUBECONFIG_PATH="${HOME}/.kube/humility-local.yaml"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

AUTH_NAMESPACE="auth-system"
AUTHENTIK_DATABASE="authentik"
BLUEPRINT_CONFIGMAP="authentik-init-114-blueprint"
POSTGRES_CLUSTER="authentik-postgres"
POSTGRES_PRIMARY_POD=""
EXPECTED_BLUEPRINTS=()

DEFAULT_OPENID_MAPPING="authentik default OAuth Mapping: OpenID 'openid'"
DEFAULT_EMAIL_MAPPING="authentik default OAuth Mapping: OpenID 'email'"
DEFAULT_PROFILE_MAPPING="authentik default OAuth Mapping: OpenID 'profile'"
POMERIUM_DISCORD_MAPPING="server-manager-pomerium-discord_user_id"
APPLICANT_DISCORD_MAPPING="server-manager-applicant-discord_user_id"

usage() {
  cat <<'EOF'
Usage: validate_authentik_blueprints_local.sh [--kubeconfig PATH] [--channel local]

Validates Authentik runtime blueprint health in the local channel:
  - every mounted init-* blueprint has a successful BlueprintInstance row
  - each blueprint has a non-empty last_applied_hash
  - custom Discord scope mappings exist and are bound to their providers
  - application slug pomerium links to provider pomerium
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
      --channel)
        [[ $# -ge 2 ]] || die "--channel requires a value"
        CHANNEL_REQUEST="$2"
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

kubectl_cmd() {
  kubectl --kubeconfig "$KUBECONFIG_PATH" "$@"
}

psql_query() {
  kubectl_cmd -n "$AUTH_NAMESPACE" exec -i "$POSTGRES_PRIMARY_POD" -c postgres -- \
    psql -U postgres -d "$AUTHENTIK_DATABASE" -v ON_ERROR_STOP=1 -At -F '|' "$@"
}

psql_scalar() {
  local output
  output="$(psql_query "$@")"
  printf '%s' "$output"
}

print_blueprint_diagnostics() {
  local blueprint_name="$1"

  echo "Blueprint diagnostics for ${blueprint_name}:" >&2
  psql_query -v blueprint_name="$blueprint_name" -P pager=off -x <<'SQL' >&2 || true
SELECT name,
       path,
       status,
       COALESCE(last_applied_hash, '') AS last_applied_hash,
       COALESCE(context::text, '') AS context,
       COALESCE(content, '') AS content
  FROM authentik_blueprints_blueprintinstance
 WHERE name = :'blueprint_name';
SQL

  echo "Recent Authentik worker log lines mentioning ${blueprint_name}:" >&2
  kubectl_cmd -n "$AUTH_NAMESPACE" logs \
    -l 'app.kubernetes.io/name=authentik,app.kubernetes.io/component=worker' \
    --tail=300 --prefix=true 2>/dev/null \
    | grep -i -- "$blueprint_name" >&2 || true
}

die_blueprint() {
  local message="$1"
  local blueprint_name="$2"

  fail "$message"
  print_blueprint_diagnostics "$blueprint_name"
  finish
  exit 1
}

load_expected_blueprints() {
  local keys

  keys="$(kubectl_cmd -n "$AUTH_NAMESPACE" get configmap "$BLUEPRINT_CONFIGMAP" \
    -o go-template='{{range $k, $_ := .data}}{{println $k}}{{end}}' 2>/dev/null)" \
    || die "blueprint ConfigMap ${BLUEPRINT_CONFIGMAP} not found"

  mapfile -t EXPECTED_BLUEPRINTS < <(
    printf '%s\n' "$keys" \
      | sed -n 's/^\(init-.*\)\.ya\?ml$/\1/p' \
      | sort
  )

  [[ "${#EXPECTED_BLUEPRINTS[@]}" -gt 0 ]] \
    || die "no init-* blueprints found in ConfigMap ${BLUEPRINT_CONFIGMAP}"
}

resolve_postgres_primary() {
  POSTGRES_PRIMARY_POD="$(kubectl_cmd -n "$AUTH_NAMESPACE" get pods \
    -l "cnpg.io/cluster=${POSTGRES_CLUSTER},role=primary" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  [[ -n "$POSTGRES_PRIMARY_POD" ]] \
    || die "CNPG primary pod not found for ${POSTGRES_CLUSTER}"
  pass "selected Authentik Postgres primary pod ${POSTGRES_PRIMARY_POD}"
}

assert_blueprint_instances() {
  local blueprint_name
  local row
  local status
  local last_applied_hash

  load_expected_blueprints
  for blueprint_name in "${EXPECTED_BLUEPRINTS[@]}"; do
    row="$(psql_scalar -v blueprint_name="$blueprint_name" <<'SQL'
SELECT status || '|' || COALESCE(last_applied_hash, '')
  FROM authentik_blueprints_blueprintinstance
 WHERE name = :'blueprint_name';
SQL
)"
    [[ -n "$row" ]] || die "missing init blueprint: ${blueprint_name}"
    pass "init blueprint exists: ${blueprint_name}"

    status="${row%%|*}"
    last_applied_hash="${row#*|}"
    if [[ "$status" != "successful" ]]; then
      die_blueprint "blueprint ${blueprint_name} status=${status} (expected successful)" "$blueprint_name"
    fi
    pass "blueprint ${blueprint_name} status is successful"

    if [[ -z "$last_applied_hash" ]]; then
      die_blueprint "blueprint ${blueprint_name} last_applied_hash is empty" "$blueprint_name"
    fi
    pass "blueprint ${blueprint_name} last_applied_hash is non-empty"
  done
}

assert_scope_mapping_exists() {
  local mapping_name="$1"
  local exists

  exists="$(psql_scalar -v mapping_name="$mapping_name" <<'SQL'
SELECT EXISTS (
  SELECT 1
    FROM authentik_core_propertymapping
   WHERE name = :'mapping_name'
);
SQL
)"
  [[ "$exists" == "t" ]] || die "scope mapping missing: ${mapping_name}"
  pass "scope mapping exists: ${mapping_name}"
}

provider_has_mapping() {
  local provider_name="$1"
  local mapping_name="$2"

  psql_scalar -v provider_name="$provider_name" -v mapping_name="$mapping_name" <<'SQL'
SELECT EXISTS (
  SELECT 1
    FROM authentik_core_provider provider
    JOIN authentik_core_provider_property_mappings provider_mapping
      ON provider_mapping.provider_id = provider.id
    JOIN authentik_core_propertymapping property_mapping
      ON property_mapping.pm_uuid = provider_mapping.propertymapping_id
   WHERE provider.name = :'provider_name'
     AND property_mapping.name = :'mapping_name'
);
SQL
}

assert_provider_mappings() {
  local provider_name="$1"
  shift
  local mapping_name
  local has_mapping

  for mapping_name in "$@"; do
    has_mapping="$(provider_has_mapping "$provider_name" "$mapping_name")"
    [[ "$has_mapping" == "t" ]] \
      || die "provider ${provider_name} missing scope mapping: ${mapping_name}"
    pass "provider ${provider_name} has scope mapping: ${mapping_name}"
  done
}

assert_pomerium_application_provider_link() {
  local expected_provider_id
  local actual_provider_id
  local pointing_at

  expected_provider_id="$(psql_scalar <<'SQL'
SELECT id
  FROM authentik_core_provider
 WHERE name = 'pomerium'
 ORDER BY id
 LIMIT 1;
SQL
)"
  actual_provider_id="$(psql_scalar <<'SQL'
SELECT COALESCE(provider_id::text, '<null>')
  FROM authentik_core_application
 WHERE slug = 'pomerium'
 ORDER BY name
 LIMIT 1;
SQL
)"

  if [[ -z "$actual_provider_id" ]]; then
    pointing_at="<missing>"
  else
    pointing_at="$actual_provider_id"
  fi

  if [[ -z "$expected_provider_id" || "$actual_provider_id" != "$expected_provider_id" ]]; then
    [[ -n "$expected_provider_id" ]] || expected_provider_id="<missing>"
    die "application pomerium provider link missing or pointing at ${pointing_at} (expected pomerium provider id ${expected_provider_id})"
  fi
  pass "application pomerium links to provider pomerium"
}

main() {
  parse_args "$@"
  [[ "$CHANNEL_REQUEST" == "local" ]] || die "unsupported channel: ${CHANNEL_REQUEST}"
  command -v kubectl >/dev/null 2>&1 || die "kubectl is required"
  [[ -f "$KUBECONFIG_PATH" ]] || die "kubeconfig not found: ${KUBECONFIG_PATH}"

  resolve_postgres_primary
  assert_blueprint_instances
  assert_scope_mapping_exists "$POMERIUM_DISCORD_MAPPING"
  assert_scope_mapping_exists "$APPLICANT_DISCORD_MAPPING"
  assert_provider_mappings \
    "pomerium" \
    "$DEFAULT_OPENID_MAPPING" \
    "$DEFAULT_EMAIL_MAPPING" \
    "$DEFAULT_PROFILE_MAPPING" \
    "$POMERIUM_DISCORD_MAPPING"
  assert_provider_mappings \
    "server-manager-applicant" \
    "$DEFAULT_OPENID_MAPPING" \
    "$DEFAULT_EMAIL_MAPPING" \
    "$DEFAULT_PROFILE_MAPPING" \
    "$APPLICANT_DISCORD_MAPPING"
  assert_pomerium_application_provider_link
  finish
}

main "$@"
