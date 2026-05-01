# BL-012 hookpoints

## Summary

BL-012 lands inside two existing test-layer files. The validator
(`infra/tests/validate_access_policy_local.sh`) already runs a live
OPAL `/v1/is_authorized` proof pod gated on `/v1/policies` hydration,
and the public-intake fixture
(`infra/tests/test_public_intake_policy_fixture.py`) already collects
under the standard `infra/tests/` pytest lane. Every machinery piece
the slice needs — the `wait_for_policy_ids` hydration gate, the
`init-115-cedar` proof pod, the `cedar_proof_command` HEREDOC, the
`--env=` payload injection idiom, the `sleep 31` polling-interval
recheck, the log-line cardinality and `.decision` jq checks, the
matrix-driven Cedar-literal constants in pytest — exists today and is
reused verbatim. The new code is two payload variables, four curl
invocations, four printf log lines, two pod env injections, two
cardinality assertions, and two-to-four `.decision` jq checks in the
validator, plus a single pytest assertion flip (or a new sibling guard
file) that inverts the existing "validator omits" check into "validator
contains." No production code, GitOps manifest, OPAL image, Helm
value, Cedar schema, or policy bundle is modified.

The four audit findings (F1–F4) map onto specific hookpoints in this
plan: F1 is a documentation alignment in the proposal, F2 is a
failure-message string extension at the validator's two new `die`
sites, F3 is a strengthening of the pytest guard's substring match
into a parsed-payload or wired-probe assertion, and F4 is an explicit
choice at the validator's round-2 jq site about whether to assert
`.decision` on both rounds.

## Reuse

### Existing OPAL probe machinery

All hosting machinery lives in
`infra/tests/validate_access_policy_local.sh` and is reused without
modification:

- **Hydration gate** —
  `wait_for_policy_ids` shell function at
  `infra/tests/validate_access_policy_local.sh:197-219`. Polls
  `http://opal-client:8180/v1/policies` for up to 120 seconds and
  asserts every expected canonical policy ID appears. Public probes
  inherit this gate without change because
  `expected_policy_ids_json()` (lines 60-67) derives expected IDs
  from `policies.json`, which already contains the
  `public-intake-allow` and `public-intake-no-read` entries
  (`policy/cedar/channels/local/services/server-manager-api/policies.json:10-17`,
  pinned by `test_public_intake_policy_fixture.py:68-83`). No
  validator change needed for hydration coverage of the public
  policies — they are already in the expected-ID set the gate
  enforces.

- **Proof pod kubectl invocation** —
  `kubectl run init-115-cedar` block at
  `infra/tests/validate_access_policy_local.sh:232-240`. The pod uses
  `curlimages/curl:8.19.0` and runs the `cedar_proof_command`
  HEREDOC. Public probes run in this same pod; no new pod is
  created.

- **`--env=` payload injection idiom** —
  the existing pattern at lines 237-239 (`EXPECTED_POLICY_IDS`,
  `ALLOW_PAYLOAD`, `DENY_PAYLOAD`) is reused for two new pod-internal
  env injections (`PUBLIC_SUBMIT_PAYLOAD`, `PUBLIC_READ_PAYLOAD` or
  equivalent names). These are pod-internal shell environment, not
  deployment env, ConfigMap, Secret, or InfisicalSecret — they live
  and die with the proof pod.

- **Polling-interval recheck cadence** —
  `sleep 31` at line 223, sandwiched between two
  `wait_for_policy_ids` calls and two probe rounds. Public probes
  run in both rounds, mirroring the existing `User::` `allow=` /
  `deny=` / `allow_after_poll=` / `deny_after_poll=` cadence
  (lines 221-226 and 227-230).

- **Curl `is_authorized` POST shape** —
  `curl -fsS -X POST -H "Content-Type: application/json"
  --data-binary @- http://opal-client:8180/v1/is_authorized` at
  lines 221-222 and 225-226. New curl invocations copy this exact
  shape; the only delta is the payload env var name.

- **Log-line cardinality assertion idiom** —
  `grep -c '^allow=' <<<"$cedar_logs"` and the
  `[[ "$allow_count" == "1" ]] || die ...` shell pattern at
  lines 247-250. New cardinality assertions follow the same shape
  with new log-line prefixes.

- **`.decision` jq check idiom** —
  `jq -e '.decision == "Allow"' <<<"${allowed_body#allow=}" >/dev/null
  || die ...` at lines 255-256. New decision checks follow the
  same shape with new prefix-strip patterns.

- **Local-channel die-check** —
  `[[ "$channel" == "local" ]] || die "expected local channel,
  got ${channel}"` at line 106. The validator is local-channel-only
  by contract, which lets the public probe payloads hardcode
  `web-intake.local` without templating. No change.

- **Cleanup hook** —
  the `cleanup` trap at lines 50-58 already deletes
  `init-115-cedar`. No change.

### Existing pytest collection

All hosting machinery lives in
`infra/tests/test_public_intake_policy_fixture.py` (or, under the
acceptable alternate, a sibling file in the same directory) and is
reused without infrastructure addition:

- **Cedar-literal constants** —
  `PUBLIC_PRINCIPAL`, `PUBLIC_SUBMIT_ACTION`, `API_READ_ACTION`,
  `PUBLIC_RESOURCE`, `API_RESOURCE` at
  `infra/tests/test_public_intake_policy_fixture.py:15-19`. These
  are the exact Cedar literals the new probe payloads must contain.
  The pytest guard reuses them directly rather than redefining
  strings.

- **`VALIDATOR` path constant** —
  `VALIDATOR = REPO_ROOT / "infra" / "tests" / "validate_access_policy_local.sh"`
  at line 13. The guard reads this file's text via
  `VALIDATOR.read_text(encoding="utf-8")` (already exercised by
  `test_access_policy_validator_remains_matrix_driven_for_public_intake`
  at line 106) and runs the new presence assertions over the
  resulting string.

- **Risk annotation docstring style** —
  `group=TG-6; named_risk=...; level=particular-integration;
  source=...; assumptions=A5.` shape at lines 47-50, 69-72, 87-90,
  102-105. New or updated test functions inherit this annotation
  style for CI risk-coverage scanners.

- **Pytest collection lane** —
  `infra/tests/` is the existing standard pytest collection
  directory. No new conftest, marker, or fixture is added. Collection
  for either the inverted assertion (Option A) or the new sibling
  file `test_validate_access_policy_local_probes.py` (Option B) is
  automatic.

- **`_messages.SEEDED_POLICY_SOURCE_MISMATCH` import path** —
  unchanged. The guard's other validator-text assertions
  (`policies.json`, `service-identities.json`,
  `SEEDED_POLICY_SOURCE_MISMATCH`,
  `"GitOps ConfigMap policy differs from policy repo" not in`) at
  lines 108-111 stay verbatim.

- **Matrix and policy-bundle fixture tests** —
  `test_access_policy_matrix_contains_public_submit_allow_and_read_deny`
  (lines 46-65),
  `test_public_intake_policy_bundle_contains_matching_permit_and_forbid`
  (lines 68-83), and
  `test_public_intake_does_not_add_service_identity` (lines 86-98)
  remain unchanged. They cover policy-text drift; the new guard
  covers validator-script drift.

## New

### Validator probes

Hookpoint: `infra/tests/validate_access_policy_local.sh`. New code
inserts beside existing structures, not replacing them.

- **Two new payload variables** —
  Insert immediately after the existing `allow_payload` /
  `deny_payload` assignments at lines 191-192:

  ```bash
  public_submit_payload="$(jq -nc '{principal: "Public::\"web-intake.local\"", action: "Action::\"application:submit_public\"", resource: "Resource::\"server-manager-api:public-applications\""}')"
  public_read_payload="$(jq -nc '{principal: "Public::\"web-intake.local\"", action: "Action::\"api:read\"", resource: "Resource::\"server-manager-api\""}')"
  ```

- **Four new curl invocations inside `cedar_proof_command`** —
  Two inside the round-1 block (after the existing `allow=...` /
  `deny=...` assignments at lines 221-222, before `sleep 31`), two
  inside the round-2 block (after `allow_after_poll=...` /
  `deny_after_poll=...` at lines 225-226). Each invocation copies
  the existing `printf "%s" "$<VAR>" | curl -fsS -X POST -H
  "Content-Type: application/json" --data-binary @-
  http://opal-client:8180/v1/is_authorized` shape with the new
  `PUBLIC_SUBMIT_PAYLOAD` / `PUBLIC_READ_PAYLOAD` env names.

- **Four new printf log lines** —
  Insert after the existing `printf "deny_after_poll=%s\n"` at line
  230. Suggested prefixes: `public_submit=`, `public_read=`,
  `public_submit_after_poll=`, `public_read_after_poll=`.

- **Two new `--env=` injections on `kubectl run`** —
  Insert after `--env="DENY_PAYLOAD=${deny_payload}"` at line 239:

  ```bash
    --env="PUBLIC_SUBMIT_PAYLOAD=${public_submit_payload}" \
    --env="PUBLIC_READ_PAYLOAD=${public_read_payload}" \
  ```

- **Two new cardinality assertions** —
  Insert after the existing `[[ "$deny_count" == "1" ]] || die ...`
  at line 250. Failure wording per proposal §2 Q3:

  ```bash
  public_submit_count="$(grep -c '^public_submit=' <<<"$cedar_logs" || true)"
  public_read_count="$(grep -c '^public_read=' <<<"$cedar_logs" || true)"
  [[ "$public_submit_count" == "1" ]] || die "expected exactly one Cedar public submit Allow log line, found ${public_submit_count}"
  [[ "$public_read_count" == "1" ]] || die "expected exactly one Cedar public read Deny log line, found ${public_read_count}"
  ```

- **Two new `.decision` jq checks (round 1)** —
  Insert after the existing
  `jq -e '.decision == "Deny"' <<<"${denied_body#deny=}"` at line
  256. Failure wording per proposal §2 Q3 (and F2-extended for the
  resource literal):

  ```bash
  public_submit_body="$(grep '^public_submit=' <<<"$cedar_logs")"
  public_read_body="$(grep '^public_read=' <<<"$cedar_logs")"
  jq -e '.decision == "Allow"' <<<"${public_submit_body#public_submit=}" >/dev/null \
    || die "Cedar public submit runtime probe expected Allow for Public::\"web-intake.local\" application:submit_public on Resource::\"server-manager-api:public-applications\", got: ${public_submit_body#public_submit=}"
  jq -e '.decision == "Deny"' <<<"${public_read_body#public_read=}" >/dev/null \
    || die "Cedar public read runtime probe expected Deny for Public::\"web-intake.local\" api:read on Resource::\"server-manager-api\", got: ${public_read_body#public_read=}"
  ```

- **Optional round-2 `.decision` jq checks (F4 hookpoint)** —
  Same shape against `public_submit_after_poll=` / `public_read_after_poll=`
  prefixes. See "Audit findings → F4" below.

- **`pass` line for the new probe coverage** —
  Insert after the existing
  `pass "Cedar access policy enforces user rule"` at line 257:

  ```bash
  pass "Cedar access policy enforces public intake rule"
  ```

### Pytest guard

Hookpoint: either modify
`infra/tests/test_public_intake_policy_fixture.py:101-113` (Option A)
or add `infra/tests/test_validate_access_policy_local_probes.py`
(Option B). Required substrings per proposal §2 Q2:

- `Public::\"web-intake.local\"`
- `Action::\"application:submit_public\"`
- `Resource::\"server-manager-api:public-applications\"`
- `Action::\"api:read\"`
- `Resource::\"server-manager-api\"`

Reuses the existing module-level constants
(`PUBLIC_PRINCIPAL`, `PUBLIC_SUBMIT_ACTION`, `PUBLIC_RESOURCE`,
`API_READ_ACTION`, `API_RESOURCE`) so the assertion text stays in
sync with the matrix and bundle assertions in the same file.

The substring shape is the proposal-locked minimum. F3 below
identifies the strengthening hookpoint into a parsed-payload or
wired-probe assertion if the implementation chooses to close that
drift class.

## Modify in place

### Validator script line ranges

`infra/tests/validate_access_policy_local.sh`:

| Line(s) | Existing | Change |
|---|---|---|
| 191-192 | `allow_payload` / `deny_payload` `jq -nc` assignments | Insert two new `public_submit_payload` / `public_read_payload` `jq -nc` assignments immediately after. |
| 193-231 | `cedar_proof_command` HEREDOC | Insert two curl invocations (after line 222) and two more (after line 226) for the round-1 / round-2 public probes. Insert four `printf` log lines after line 230. |
| 233-240 | `kubectl run init-115-cedar` invocation | Insert `--env="PUBLIC_SUBMIT_PAYLOAD=..."` and `--env="PUBLIC_READ_PAYLOAD=..."` after line 239. |
| 247-250 | User allow/deny cardinality assertions | Insert two parallel cardinality assertions for `^public_submit=` / `^public_read=` after line 250. |
| 251-256 | User allow/deny body extraction + `.decision` jq checks | Insert public submit / public read body extraction + `.decision` jq checks after line 256. F2 hookpoint applies to the failure-message strings here. |
| (new line after 257) | `pass "Cedar access policy enforces user rule"` | Insert `pass "Cedar access policy enforces public intake rule"` after the existing `pass`. |
| 14-22, 71-95, 178-182 | `usage()`, CLI flag parsing, `--static-only` short-circuit | **No change.** Operator invocation is byte-identical pre/post. |
| 60-67 | `expected_policy_ids_json()` | **No change.** The function already derives the public policy IDs from `policies.json`. |
| 197-219 | `wait_for_policy_ids` | **No change.** Hydration gate is reused as-is. |
| 50-58 | `cleanup` trap | **No change.** Already deletes `init-115-cedar`. |

Total churn budget: ~60 lines per proposal §6.

### Test file extension points

`infra/tests/test_public_intake_policy_fixture.py`:

| Line(s) | Existing | Change (Option A) |
|---|---|---|
| 1-13 | imports, `REPO_ROOT`, `MATRIX`, `VALIDATOR` constants | **No change.** |
| 15-19 | `PUBLIC_PRINCIPAL`, `PUBLIC_SUBMIT_ACTION`, `API_READ_ACTION`, `PUBLIC_RESOURCE`, `API_RESOURCE` | **No change.** Reused directly by the inverted guard. |
| 22-43 | `_yaml`, `_repo_path`, `_policies`, `_service_identities`, `_policy_contents` helpers | **No change.** |
| 46-65 | `test_access_policy_matrix_contains_public_submit_allow_and_read_deny` | **No change.** Matrix coverage stays. |
| 68-83 | `test_public_intake_policy_bundle_contains_matching_permit_and_forbid` | **No change.** Policy bundle coverage stays. |
| 86-98 | `test_public_intake_does_not_add_service_identity` | **No change.** Service-identity scope guard stays. |
| 101-113 | `test_access_policy_validator_remains_matrix_driven_for_public_intake` | **Invert.** Replace `assert "application:submit_public" not in validator` and `assert "web-intake.local" not in validator` with positive assertions for the four required Cedar literals (use `PUBLIC_PRINCIPAL`, `PUBLIC_SUBMIT_ACTION`, `PUBLIC_RESOURCE`, `API_READ_ACTION`, `API_RESOURCE`). Keep the surrounding "policies.json", "service-identities.json", `SEEDED_POLICY_SOURCE_MISMATCH`, and `"GitOps ConfigMap policy differs from policy repo" not in` assertions verbatim. Update the test name + named_risk annotation if appropriate (e.g., `validator_public_runtime_probe_drift`). |

Under Option B, lines 101-113 stay unchanged and a new file
`infra/tests/test_validate_access_policy_local_probes.py` carries
the inverted assertions. Note: under Option B the existing
`test_access_policy_validator_remains_matrix_driven_for_public_intake`
test would still assert `"application:submit_public" not in
validator` and `"web-intake.local" not in validator`, which would
fail once the validator hardcodes the public payloads — so the
existing test must still be updated or deleted under Option B.
This makes Option A the simpler path; Option B is "Option A plus a
sibling file."

Total churn budget: ~35 lines per proposal §6.

## Audit findings (F1..) hookpoint mapping

### F1 — Read-deny probe action/resource diverge from `authorize_public_intake`

**Hookpoint:** documentation, not code.

The audit accepts F1 as an audit-criterion clarification rather than a
behavior gap. The proposal already covers the read-deny probe's
intent in §2 Q1 (the second probe is the matching forbid statement
to catch principal-type rejection asymmetry). No validator or pytest
change is required. The hookpoint, if any, is a one-line clarification
in `proposals/29-bl-012-public-entity-runtime-probe.md` §2 Q1 noting
that the read-deny probe targets the matching forbid policy and is
not a reproduction of `authorize_public_intake`'s call shape.

The validator does not template the `web-intake.{channel}` literal
because the validator is local-channel-only by contract (line 106
die-check). If the channel contract ever expands beyond `local`,
the hookpoint moves to the two payload variable assignments at
lines 191-192 (or the new public payload assignments inserted there)
to template the channel suffix.

### F2 — Failure message omits the resource literal

**Hookpoint:** the two new `die ...` failure-message strings inserted
after line 256 of `infra/tests/validate_access_policy_local.sh`.

Replace the proposal-locked wording:

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public, got: <body>
Cedar public read runtime probe expected Deny for Public::"web-intake.local" api:read, got: <body>
```

with the F2-extended wording:

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public on Resource::"server-manager-api:public-applications", got: <body>
Cedar public read runtime probe expected Deny for Public::"web-intake.local" api:read on Resource::"server-manager-api", got: <body>
```

Cost: one additional `on Resource::"..."` substring per failure path,
no script-flow change. Already shown in the round-1 jq check snippet
under "Validator probes" above.

### F3 — Pytest guard is substring-shaped, not parsed-payload-shaped

**Hookpoint:** the inverted guard test in
`infra/tests/test_public_intake_policy_fixture.py:101-113` (Option A)
or `infra/tests/test_validate_access_policy_local_probes.py`
(Option B).

Two strengthening shapes (audit F3 §Action), both within the proposal
§6 35-line pytest churn budget:

- **(a) Payload-parse guard.** Regex-extract every `jq -nc '{...}'`
  payload assignment in the validator and parse each into a dict.
  Assert the set of payload triples contains the two new public
  triples. The regex anchor is the existing `jq -nc '{principal:
  "...", action: "...", resource: "..."}'` pattern at lines 191-192
  (and the new lines inserted there). This catches comment-only
  retention because comments do not contain `jq -nc` invocations.

- **(b) Probe-wiring guard.** For each expected probe, assert the
  validator contains all of: a payload variable assignment
  (`<name>_payload="$(jq -nc ...)"`), a `--env="<NAME>_PAYLOAD=..."`
  on the `kubectl run` invocation, a `printf "<prefix>=%s\n"
  "$<var>"` log line, a `grep -c '^<prefix>=' <<<"$cedar_logs"`
  cardinality count, a `[[ "$<count>" == "1" ]] || die ...`
  assertion, and a `jq -e '.decision == "<expected>"' <<<...`
  check. This catches all four drift classes audit F3 enumerates.

The substring shape locked by proposal §2 Q2 is the floor; either
strengthening shape is the ceiling. The decision is the implementer's
per the audit's "F3 §Action."

### F4 — Second-round probe `.decision` check not explicitly locked

**Hookpoint:** the round-2 jq checks in
`infra/tests/validate_access_policy_local.sh`, inserted after the
round-1 checks at the new line ~256+N.

The proposal §3 says "Assert `.decision == "Allow"` for public
submit and `.decision == "Deny"` for public read" without specifying
round 1 vs round 2. The existing User-probe pattern only asserts
`.decision` on round 1 (lines 255-256); round 2 is printed but not
jq-checked, with cardinality as the only round-2 guard.

Two acceptable choices:

- **Lock both rounds.** Insert two more `.decision` jq checks
  against `public_submit_after_poll=` and `public_read_after_poll=`
  prefixes. Failure wording mirrors the round-1 messages with an
  `(after polling-interval recheck)` qualifier, e.g.:

  ```text
  Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public on Resource::"server-manager-api:public-applications" (after polling-interval recheck), got: <body>
  ```

  Cost: two additional jq checks (~6 lines). Closes the round-2
  decision-divergence gap with negligible script churn.

- **Document round 2 as informational.** Accept the existing
  User-probe pattern; round 2 is cardinality-guarded only. The audit
  notes this is weaker but acceptable as a continuation of the
  established lane shape. Hookpoint then reduces to a one-line
  comment in the validator script noting the asymmetry, or a
  paragraph in the proposal §3 acknowledging it.

Either choice is locked in the implementation PR, not in the
proposal.

## Anti-scope

The following surfaces are explicitly **not** hookpoints for BL-012,
per proposal §3 ("Unmodified substrate") and §5 ("Anti-scope"). Any
PR that changes these is out of scope and must be re-gated.

- **Production API code.** No edits to
  `services/api/app/services/authorization.py`,
  `services/api/app/api/v1/endpoints/applications/public.py`, or any
  other API route, contract, or auth chain. The `Public::` Cedar
  request shape is byte-identical pre/post.

- **Discord daemon, web, repository, service, or migration code.**
  Test-layer-only slice.

- **Policy generator code.** No edits to
  `infra/scripts/render-gitops-source.py`,
  `policy/cedar/...` generators, or the seeded `.cedar` source
  pipeline.

- **Cedar policy bundle.** No edits to
  `policy/cedar/channels/local/services/server-manager-api/policies.json`.
  The public permit and forbid statements at lines 10-17 already
  exist; the slice exercises them, it does not author them.

- **Service identity bundle.** No edits to
  `policy/cedar/channels/local/services/server-manager-api/service-identities.json`.
  Public intake remains not modeled as a service identity (preserved
  by the existing `test_public_intake_does_not_add_service_identity`
  guard at lines 86-98).

- **Cedar schema file.** No new schema file under `policy/`,
  `gitops/channels/local/auth/opal-cedar/`, or anywhere else. The
  repo has no Cedar schema today, and BL-012 deliberately leaves
  that absence in place — the slice is a regression detector for
  the day a future OPAL/Cedar runtime starts enforcing one.

- **GitOps manifests.** No edits to `gitops/channels/local/**`,
  including `gitops/channels/local/auth/opal-cedar/`. OPAL Helm
  values, image tags, and `OPAL_POLICY_STORE_TYPE=CEDAR` knob remain
  unchanged.

- **OPAL or Cedar versions.** No image bump, no Helm chart bump.
  BL-012 is a regression detector for runtime behavior changes, not
  an upgrade proposal.

- **Authentik blueprint, Pomerium routes, or Kong ingress.**
  Test-layer-only slice. No public-intake auth chain or rate-limit
  binding is touched.

- **Validator CLI surface.** No new flags, no removed flags, no
  renamed flags. `usage()` text is preserved (or extended only
  additively, if at all). `--static-only` posture is explicitly
  preserved (proposal §2 Q1: "`--static-only` remains static-only
  and does not attempt to catch OPAL/Cedar runtime behavior").

- **Validator generalization into a matrix runner.** Anti-scoped
  per proposal §5: "Do not convert the validator into a full matrix
  runner in this slice." The new payloads are real, hardcoded entries
  beside the existing hardcoded `User::` payloads — not a
  half-implemented "matrix runner skeleton" with a TODO.

- **Tenant or service-identity validators.** No edits to
  `infra/tests/validate_tenant_isolation_local.sh`,
  `infra/scripts/verify-service-identity-claim.sh`, or
  `infra/tests/test_tenant_policy_source_contract.py`. Tenant,
  TenantChannel, User, and Service runtime coverage stays on its
  existing paths.

- **`infra/tests/test_access_policy_contract.py` and
  `infra/tests/test_cedar_seeded_source_equality.py`.** No edits.
  These cover policy-text and seeded-source equality and are not
  affected by adding live runtime probes.

- **Pytest infrastructure.** No new conftest, marker, fixture
  module, or `infra/tests/_messages.py` constant. The guard reuses
  existing module-level constants.

HOOKPOINTS_DONE: research/43-bl-012-hookpoints.md
