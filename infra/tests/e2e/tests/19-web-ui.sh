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
  # psql variable substitutions are expanded when SQL is read from stdin.
  row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v application_id="$application_id" -At -F $'\t' <<'SQL'
SELECT a.state, a.applicant_id, m.kind, m.discord_user_id
  FROM applications a
  JOIN members m ON m.id = a.applicant_id
 WHERE a.id = :'application_id'::uuid
   AND m.kind = 'discord';
SQL
  )"
  [[ -n "$row" ]] || e2e_fail "public submit application row not found: ${application_id}"
  IFS=$'\t' read -r state applicant_id member_kind discord_user_id <<<"$row"
  [[ "$state" == "approved" ]] || e2e_fail "application state expected approved after officer flow, got ${state}"
  [[ -n "$applicant_id" ]] || e2e_fail "public submit applicant_id missing"
  [[ "$member_kind" == "discord" ]] || e2e_fail "public submit applicant member kind expected discord, got ${member_kind}"
  [[ "$discord_user_id" == "$expected_discord_user_id" ]] || e2e_fail "public submit Discord user expected ${expected_discord_user_id}, got ${discord_user_id}"
  [[ "$discord_user_id" != public:* ]] || e2e_fail "public submit applicant member must not be synthetic: ${discord_user_id}"

  local notification_row event_count officer_envelopes applicant_envelopes delivery_effects
  notification_row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" \
      -v ON_ERROR_STOP=1 \
      -v application_id="$application_id" \
      -v expected_discord_user_id="$expected_discord_user_id" \
      -v applications_review_channel_id="$E2E_APPLICATIONS_REVIEW_CHANNEL_ID" \
      -At -F $'\t' <<'SQL'
WITH matching_events AS (
  SELECT id
    FROM notification_events
   WHERE event_type = 'application.public_submitted'
     AND payload_json->>'application_id' = :'application_id'
),
matching_envelopes AS (
  SELECT ne.*
    FROM notification_envelopes ne
    JOIN matching_events me ON me.id = ne.source_event_id
)
SELECT
  (SELECT count(*) FROM matching_events),
  (SELECT count(*)
     FROM matching_envelopes
    WHERE channel = 'designated_channel'
      AND destination_channel_id = :'applications_review_channel_id'
      AND rendered_embed_json IS NOT NULL),
  (SELECT count(*)
     FROM matching_envelopes
    WHERE channel = 'dm'
      AND recipient_discord_id = :'expected_discord_user_id'),
  (SELECT count(*)
     FROM deferred_effects de
     JOIN matching_envelopes me ON de.payload_json->>'envelope_id' = me.id::text
    WHERE de.effect_type = 'notifications_deliver');
SQL
  )"
  IFS=$'\t' read -r event_count officer_envelopes applicant_envelopes delivery_effects <<<"$notification_row"
  [[ "$event_count" == "1" ]] || e2e_fail "expected one application.public_submitted event for ${application_id}, got ${event_count}"
  [[ "$officer_envelopes" == "1" ]] || e2e_fail "expected one officer designated-channel notification envelope for ${application_id}, got ${officer_envelopes}"
  [[ "$applicant_envelopes" == "1" ]] || e2e_fail "expected one applicant DM notification envelope for ${application_id}, got ${applicant_envelopes}"
  [[ "$delivery_effects" == "2" ]] || e2e_fail "expected two queued notification delivery effects for ${application_id}, got ${delivery_effects}"
  e2e_pass "public submit persisted real Discord applicant ${applicant_id}"
}

assert_officer_review_persisted() {
  local record_file="${REPO_ROOT}/infra/tests/e2e/playwright/sessions/web-ui-queue-claim.json"
  [[ -f "$record_file" ]] || e2e_fail "officer claim record missing: ${record_file}"
  local detail_record="${REPO_ROOT}/infra/tests/e2e/playwright/sessions/web-ui-detail.json"
  [[ -f "$detail_record" ]] || e2e_fail "officer detail record missing: ${detail_record}"

  local application_id expected_officer_discord_user_id officer_message
  application_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).claimed_application_id)' "$record_file")"
  expected_officer_discord_user_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).officer_discord_user_id)' "$record_file")"
  officer_message="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).officer_message)' "$detail_record")"
  [[ -n "$application_id" ]] || e2e_fail "officer claim application_id missing"
  [[ -n "$expected_officer_discord_user_id" ]] || e2e_fail "officer Discord user id missing"
  [[ -n "$officer_message" ]] || e2e_fail "officer message missing from detail record"

  local primary_pod url row state applicant_id owner_id applicant_kind applicant_discord_user_id owner_kind owner_discord_user_id
  primary_pod="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get pods -l 'cnpg.io/cluster=server-manager-postgres,role=primary' -o jsonpath='{.items[0].metadata.name}')"
  url="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-postgres-url -o jsonpath='{.data.url}' | base64 -d)"
  row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v application_id="$application_id" -At -F $'\t' <<'SQL'
SELECT a.state,
       a.applicant_id,
       a.owner_id,
       applicant.kind,
       applicant.discord_user_id,
       owner.kind,
       owner.discord_user_id
  FROM applications a
  JOIN members applicant ON applicant.id = a.applicant_id
  JOIN members owner ON owner.id = a.owner_id
 WHERE a.id = :'application_id'::uuid;
SQL
  )"
  [[ -n "$row" ]] || e2e_fail "claimed application row not found: ${application_id}"
  IFS=$'\t' read -r state applicant_id owner_id applicant_kind applicant_discord_user_id owner_kind owner_discord_user_id <<<"$row"
  [[ "$state" == "approved" ]] || e2e_fail "officer flow state expected approved, got ${state}"
  [[ -n "$owner_id" ]] || e2e_fail "officer claim owner_id missing"
  [[ "$applicant_id" != "$owner_id" ]] || e2e_fail "officer claim owner_id must differ from applicant_id"
  [[ "$applicant_kind" == "discord" ]] || e2e_fail "applicant member kind expected discord, got ${applicant_kind}"
  [[ "$owner_kind" == "discord" ]] || e2e_fail "owner member kind expected discord, got ${owner_kind}"
  [[ "$applicant_discord_user_id" == "$E2E_APPLICANT_DISCORD_USER_ID" ]] || e2e_fail "applicant Discord user expected ${E2E_APPLICANT_DISCORD_USER_ID}, got ${applicant_discord_user_id}"
  [[ "$owner_discord_user_id" == "$expected_officer_discord_user_id" ]] || e2e_fail "owner Discord user expected ${expected_officer_discord_user_id}, got ${owner_discord_user_id}"

  local audit_row
  audit_row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v application_id="$application_id" -At -F $'\t' <<'SQL'
SELECT request_surface
  FROM activity_actions
 WHERE aggregate_type = 'application'
   AND aggregate_id = :'application_id'::uuid
   AND action_type = 'application.claim'
 ORDER BY recorded_at DESC
 LIMIT 1;
SQL
  )"
  [[ "$audit_row" == "api:/api/v1/web/officer/applications/${application_id}/claim" ]] || e2e_fail "officer claim audit request_surface mismatch: ${audit_row}"
  local review_audit_row
  review_audit_row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v application_id="$application_id" -At -F $'\t' <<'SQL'
SELECT request_surface
  FROM activity_actions
 WHERE aggregate_type = 'application'
   AND aggregate_id = :'application_id'::uuid
   AND action_type = 'application.review'
 ORDER BY recorded_at DESC
 LIMIT 1;
SQL
  )"
  [[ "$review_audit_row" == "api:/api/v1/web/officer/applications/${application_id}/transitions" ]] || e2e_fail "officer review audit request_surface mismatch: ${review_audit_row}"

  local message_row
  message_row="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v application_id="$application_id" -v body_markdown="$officer_message" -At -F $'\t' <<'SQL'
SELECT visibility, body_markdown
  FROM application_messages
 WHERE application_id = :'application_id'::uuid
   AND body_markdown = :'body_markdown'
 ORDER BY message_seq DESC
 LIMIT 1;
SQL
  )"
  [[ -n "$message_row" ]] || e2e_fail "officer message row not found for ${application_id}"
  local message_visibility message_body
  IFS=$'\t' read -r message_visibility message_body <<<"$message_row"
  [[ "$message_visibility" == "officer_only" ]] || e2e_fail "officer message visibility expected officer_only, got ${message_visibility}"
  [[ "$message_body" == "$officer_message" ]] || e2e_fail "officer message body mismatch: ${message_body}"
  e2e_pass "officer reviewed and approved application ${application_id} as Discord member ${owner_id}"
}

grant_officer_message_authority() {
  local seed_file="/tmp/seed-officer-authority.json"
  [[ -f "$seed_file" ]] || e2e_fail "officer authority seed record missing: ${seed_file}"

  local officer_member_id grant_id primary_pod url
  officer_member_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).member_id)' "$seed_file")"
  grant_id="$(node -e 'console.log(require("crypto").randomUUID())')"
  [[ -n "$officer_member_id" ]] || e2e_fail "officer authority seed missing member_id"
  primary_pod="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get pods -l 'cnpg.io/cluster=server-manager-postgres,role=primary' -o jsonpath='{.items[0].metadata.name}')"
  url="$(kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-postgres-url -o jsonpath='{.data.url}' | base64 -d)"

  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager exec -i "$primary_pod" -c postgres -- \
    psql "$url" -v ON_ERROR_STOP=1 -v grant_id="$grant_id" -v officer_member_id="$officer_member_id" -At <<'SQL' >/tmp/grant-officer-message-authority.out
INSERT INTO authority_grants (
  id,
  grantee_id,
  scope_kind,
  scope_id,
  permissions,
  expires_at,
  revoked_at,
  revoked_by,
  revocation_reason,
  predecessor_grant_id
)
SELECT :'grant_id'::uuid,
       :'officer_member_id',
       'global',
       NULL,
       '["application.message"]'::jsonb,
       NULL,
       NULL,
       NULL,
       NULL,
       NULL
 WHERE NOT EXISTS (
   SELECT 1
     FROM authority_grants
    WHERE grantee_id = :'officer_member_id'
      AND scope_kind = 'global'
      AND scope_id IS NULL
      AND permissions = '["application.message"]'::jsonb
      AND revoked_at IS NULL
 );
SQL
  e2e_pass "seeded officer application.message authority"
}

assert_officer_detail_checked() {
  local record_file="${REPO_ROOT}/infra/tests/e2e/playwright/sessions/web-ui-detail.json"
  [[ -f "$record_file" ]] || e2e_fail "officer detail record missing: ${record_file}"

  local application_id detail_state transcript_claimed
  application_id="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).claimed_application_id)' "$record_file")"
  detail_state="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).detail_state)' "$record_file")"
  transcript_claimed="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).transcript_claimed_state_change)' "$record_file")"
  [[ -n "$application_id" ]] || e2e_fail "officer detail application_id missing"
  [[ "$detail_state" == *approved* ]] || e2e_fail "officer detail state expected approved, got ${detail_state}"
  [[ "$transcript_claimed" == "true" ]] || e2e_fail "officer detail transcript claim state-change missing"
  local transcript_reviewed transcript_approved
  transcript_reviewed="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).transcript_review_state_change)' "$record_file")"
  transcript_approved="$(node -e 'const fs = require("fs"); console.log(JSON.parse(fs.readFileSync(process.argv[1], "utf8")).transcript_approved_state_change)' "$record_file")"
  [[ "$transcript_reviewed" == "true" ]] || e2e_fail "officer detail transcript review state-change missing"
  [[ "$transcript_approved" == "true" ]] || e2e_fail "officer detail transcript approved state-change missing"
  e2e_pass "officer detail rendered approved state and transcript for ${application_id}"
}

export E2E_APPLICANT_RECEIPT_SIGNING_KEY="$(
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-e2e-fixtures \
    -o jsonpath='{.data.applicant-receipt-signing-key}' | base64 -d
)"
export E2E_APPLICANT_DISCORD_USER_ID="$(
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-e2e-fixtures \
    -o jsonpath='{.data.applicant-discord-user-id}' | base64 -d
)"
export E2E_APPLICATIONS_REVIEW_CHANNEL_ID="$(
  kubectl --kubeconfig "$KUBECONFIG_PATH" -n server-manager get secret server-manager-e2e-fixtures \
    -o jsonpath='{.data.applications-review-channel-id}' | base64 -d
)"
export E2E_OFFICER_DISCORD_USER_ID="$(
  node -e 'const fs = require("fs"); const value = JSON.parse(fs.readFileSync(process.argv[1], "utf8")).auth?.identity?.discord_user_id; if (value !== undefined && value !== null && String(value).trim() !== "") console.log(value);' \
    "${REPO_ROOT}/infra/tests/fixtures/web-ui/contract.json"
)"
[[ -n "$E2E_APPLICANT_RECEIPT_SIGNING_KEY" ]] || e2e_fail "server-manager-e2e-fixtures missing applicant-receipt-signing-key"
[[ -n "$E2E_APPLICANT_DISCORD_USER_ID" ]] || e2e_fail "server-manager-e2e-fixtures missing applicant-discord-user-id"
[[ -n "$E2E_APPLICATIONS_REVIEW_CHANNEL_ID" ]] || e2e_fail "server-manager-e2e-fixtures missing applications-review-channel-id"
[[ -n "$E2E_OFFICER_DISCORD_USER_ID" && "$E2E_OFFICER_DISCORD_USER_ID" != "undefined" ]] || e2e_fail "web UI contract fixture missing officer Discord user id"

run_validator validate-web-ui infra/tests/validate_web_ui_local.sh --kubeconfig "$KUBECONFIG_PATH" --tag init-118-local --skip-image-build
KUBECONFIG_PATH="$KUBECONFIG_PATH" E2E_OFFICER_DISCORD_USER_ID="$E2E_OFFICER_DISCORD_USER_ID" \
  node "${REPO_ROOT}/infra/tests/e2e/lib/seed-authority-grants.mjs" >/tmp/seed-officer-authority.json
e2e_pass "seeded officer application.claim/application.review/application.approve/application.message authority"
grant_officer_message_authority
"${REPO_ROOT}/infra/tests/e2e/lib/playwright/run-browser-flow.sh" web-ui "$KUBECONFIG_PATH" "$(e2e_log_path playwright-web-ui)"
assert_public_submit_persisted
assert_officer_review_persisted
assert_officer_detail_checked
e2e_pass "Playwright completed web UI OAuth and navigation flow"
e2e_finish
