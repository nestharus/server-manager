#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
e2e_init "19-web-ui" "SPA public and authenticated admin UI"

assert_public_submit_persisted() {
  local record_file="${REPO_ROOT}/infra/tests/e2e/playwright/sessions/web-ui-public-submit.json"
  [[ -f "$record_file" ]] || e2e_fail "public submit record missing: ${record_file}"

  local application_id expected_discord_user_id
  application_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).application_id)' "$record_file")"
  expected_discord_user_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).applicant_discord_user_id)' "$record_file")"
  [[ -n "$application_id" ]] || e2e_fail "public submit application_id missing"
  [[ -n "$expected_discord_user_id" ]] || e2e_fail "public submit applicant_discord_user_id missing"

  local primary_pod url row state applicant_id member_kind discord_user_id
  primary_pod="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get pods -l 'cnpg.io/cluster=server-manager-postgres,role=primary' -o jsonpath='{.items[0].metadata.name}')"
  url="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-postgres-url -o jsonpath='{.data.url}' | base64 -d)"
  # NOTE: psql does NOT expand `:'var'` / `:var` substitutions in `-c "..."`
  # queries — only when reading SQL from a file or stdin. Use shell
  # interpolation (`'${var}'`) inside the `-c` payload instead. Was a real
  # bug in this very file pre-BL-007.
  row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -At -F $'\t' -c \
    "SELECT a.state, a.applicant_id, m.kind, m.discord_user_id FROM applications a JOIN members m ON m.id = a.applicant_id WHERE a.id = '${application_id}'::uuid AND m.kind = 'discord';" \
  )"
  [[ -n "$row" ]] || e2e_fail "public submit application row not found: ${application_id}"
  IFS=$'\t' read -r state applicant_id member_kind discord_user_id <<<"$row"
  [[ "$state" == "queued" ]] || e2e_fail "public submit application state expected queued, got ${state}"
  [[ -n "$applicant_id" ]] || e2e_fail "public submit applicant_id missing"
  [[ "$member_kind" == "discord" ]] || e2e_fail "public submit applicant member kind expected discord, got ${member_kind}"
  [[ "$discord_user_id" == "$expected_discord_user_id" ]] || e2e_fail "public submit Discord user expected ${expected_discord_user_id}, got ${discord_user_id}"
  [[ "$discord_user_id" != public:* ]] || e2e_fail "public submit applicant member must not be synthetic: ${discord_user_id}"
  e2e_pass "public submit persisted queued application with real Discord member ${applicant_id}"
}

assert_officer_claim_persisted() {
  local record_file="${REPO_ROOT}/infra/tests/e2e/playwright/sessions/web-ui-queue-claim.json"
  [[ -f "$record_file" ]] || e2e_fail "officer claim record missing: ${record_file}"

  local application_id expected_officer_discord_user_id
  application_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).claimed_application_id)' "$record_file")"
  expected_officer_discord_user_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).officer_discord_user_id)' "$record_file")"
  [[ -n "$application_id" ]] || e2e_fail "officer claim application_id missing"
  [[ -n "$expected_officer_discord_user_id" ]] || e2e_fail "officer Discord user id missing"

  local primary_pod url row state applicant_id owner_id applicant_kind applicant_discord_user_id owner_kind owner_discord_user_id
  primary_pod="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get pods -l 'cnpg.io/cluster=server-manager-postgres,role=primary' -o jsonpath='{.items[0].metadata.name}')"
  url="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-postgres-url -o jsonpath='{.data.url}' | base64 -d)"
  row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -At -F $'\t' -c \
    "SELECT a.state, a.applicant_id, a.owner_id, applicant.kind, applicant.discord_user_id, owner.kind, owner.discord_user_id FROM applications a JOIN members applicant ON applicant.id = a.applicant_id JOIN members owner ON owner.id = a.owner_id WHERE a.id = '${application_id}'::uuid;" \
  )"
  [[ -n "$row" ]] || e2e_fail "claimed application row not found: ${application_id}"
  IFS=$'\t' read -r state applicant_id owner_id applicant_kind applicant_discord_user_id owner_kind owner_discord_user_id <<<"$row"
  [[ "$state" == "claimed" ]] || e2e_fail "officer claim state expected claimed, got ${state}"
  [[ -n "$owner_id" ]] || e2e_fail "officer claim owner_id missing"
  [[ "$applicant_id" != "$owner_id" ]] || e2e_fail "officer claim owner_id must differ from applicant_id"
  [[ "$applicant_kind" == "discord" ]] || e2e_fail "applicant member kind expected discord, got ${applicant_kind}"
  [[ "$owner_kind" == "discord" ]] || e2e_fail "owner member kind expected discord, got ${owner_kind}"
  [[ "$applicant_discord_user_id" == "$E2E_APPLICANT_DISCORD_USER_ID" ]] || e2e_fail "applicant Discord user expected ${E2E_APPLICANT_DISCORD_USER_ID}, got ${applicant_discord_user_id}"
  [[ "$owner_discord_user_id" == "$expected_officer_discord_user_id" ]] || e2e_fail "owner Discord user expected ${expected_officer_discord_user_id}, got ${owner_discord_user_id}"
  e2e_pass "officer queue claimed application ${application_id} as Discord member ${owner_id}"
}

export E2E_APPLICANT_RECEIPT_SIGNING_KEY="$(
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-e2e-fixtures \
    -o jsonpath='{.data.applicant-receipt-signing-key}' | base64 -d
)"
export E2E_APPLICANT_DISCORD_USER_ID="$(
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-e2e-fixtures \
    -o jsonpath='{.data.applicant-discord-user-id}' | base64 -d
)"
export E2E_OFFICER_DISCORD_USER_ID="$(
  node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).auth.identity.discord_user_id)' \
    "${REPO_ROOT}/infra/tests/fixtures/web-ui/contract.json"
)"
[[ -n "$E2E_APPLICANT_RECEIPT_SIGNING_KEY" ]] || e2e_fail "server-manager-e2e-fixtures missing applicant-receipt-signing-key"
[[ -n "$E2E_APPLICANT_DISCORD_USER_ID" ]] || e2e_fail "server-manager-e2e-fixtures missing applicant-discord-user-id"
[[ -n "$E2E_OFFICER_DISCORD_USER_ID" ]] || e2e_fail "web UI contract fixture missing officer Discord user id"

run_validator validate-web-ui infra/tests/validate_web_ui_local.sh --kubeconfig "$KUBECONFIG_PATH" --tag init-118-local --skip-image-build
KUBECONFIG_PATH="$KUBECONFIG_PATH" E2E_OFFICER_DISCORD_USER_ID="$E2E_OFFICER_DISCORD_USER_ID" \
  node "${REPO_ROOT}/infra/tests/e2e/lib/seed-authority-grants.mjs" >/tmp/seed-officer-authority.json
e2e_pass "seeded officer application.review/application.claim authority"
"${REPO_ROOT}/infra/tests/e2e/lib/playwright/run-browser-flow.sh" web-ui "$KUBECONFIG_PATH" "$(e2e_log_path playwright-web-ui)"
assert_public_submit_persisted
assert_officer_claim_persisted
e2e_pass "Playwright completed web UI OAuth and navigation flow"
e2e_finish
