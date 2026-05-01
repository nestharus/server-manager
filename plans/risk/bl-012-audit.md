# BL-012 — Audit risk gate

**Verdict:** LOW (with four findings, none blocking)

Scope: BL-012 — add a live OPAL/Cedar runtime probe for
the `Public::` principal so a future
schema/entity-registry enforcement that rejects
`Public::"web-intake.local"` is caught in the access-policy
runtime lane rather than at production submit. The slice
extends `infra/tests/validate_access_policy_local.sh` with
two live `/v1/is_authorized` probes (Public submit Allow,
Public read Deny) and adds a pytest guard that asserts the
validator script contains both probe payloads.

The audit gate inspects: (1) probe payloads exactly match
the principal/action/resource used by
`authorize_public_intake`, (2) probes run only after
`/v1/policies` confirms hydration, (3) failure messages
name the exact triple for operator debugging, (4) the
pytest guard catches drift rather than passing on
incidental substrings, and (5) no false-positive scenarios
(OPAL eventual consistency, Cedar caching, etc.).

Source proposal:
`proposals/29-bl-012-public-entity-runtime-probe.md`.
Source problem map:
`research/42-bl-012-public-entity-problem-map.md`.
Existing validator: `infra/tests/validate_access_policy_local.sh`.
Existing static guard:
`infra/tests/test_public_intake_policy_fixture.py`.

## A1 — Probe payloads target the EXACT triple `authorize_public_intake` issues

**Production call site:**
`services/api/app/services/authorization.py:24-32` builds
the Cedar request with:

- `principal = f'Public::"web-intake.{channel}"'`, where
  `channel = getattr(settings, "platform_channel", "local")`.
  When the validator runs against the local channel
  (which it locks at line 106 of the validator:
  `[[ "$channel" == "local" ]] || die`), the principal
  resolves to `Public::"web-intake.local"`.
- `action = PUBLIC_INTAKE_ACTION = 'Action::"application:submit_public"'`.
- `resource = PUBLIC_INTAKE_RESOURCE = 'Resource::"server-manager-api:public-applications"'`.

**Submit-allow probe (proposal §2 Q1, §2 Q2):**

```json
{"principal":"Public::\"web-intake.local\"","action":"Action::\"application:submit_public\"","resource":"Resource::\"server-manager-api:public-applications\""}
```

Each of the three fields is a character-for-character match
with the production call. The Cedar literal escaping
(`\"web-intake.local\"`) is the same shape the API code
emits via the `f'Public::"web-intake.{channel}"'` template.

**Read-deny probe (proposal §2 Q1, §2 Q2):**

```json
{"principal":"Public::\"web-intake.local\"","action":"Action::\"api:read\"","resource":"Resource::\"server-manager-api\""}
```

This probe targets the matching forbid statement in the
local bundle (`policies.json:14-17`). The principal is the
same `Public::"web-intake.local"` that
`authorize_public_intake` constructs, but the action
(`api:read`) and resource (`server-manager-api`) are not
issued by `authorize_public_intake` — they are the second
public-policy guard rail asserting that a `Public::`
principal cannot read the API. The audit-gate item asks
whether the probes target the EXACT triple
`authorize_public_intake` uses. Strictly read, only the
submit-allow probe does that. The read-deny probe targets
the same `Public::` principal and the matching forbid
policy, which is the right second probe for BL-012's
scope (catching schema/entity-registry rejection of the
`Public::` principal type as a whole) but is not a
reproduction of any production call.

**Channel coupling:** the validator hardcodes
`web-intake.local` because the validator is local-channel-
only by contract (line 106 die-check). If the channel
contract changes — e.g., the platform runs an additional
canonical channel — the probe payload would need to follow
the channel template the same way `authorize_public_intake`
already does. The proposal does not template the probe
payload; this is an acceptable simplification for BL-012's
scope but is captured below as F1.

**Verdict:** Submit-allow probe is an exact production-call
reproduction. Read-deny probe is an exact match for the
same `Public::` principal against the matching forbid
policy. F1 below on the channel-template coupling.

## A2 — Probes run AFTER `/v1/policies` confirms hydration

**Existing hydration gate
(`validate_access_policy_local.sh:197-220`):** the
`wait_for_policy_ids` shell function polls
`http://opal-client:8180/v1/policies` for up to 120 seconds
(120 × 1s sleep) and asserts every expected canonical
policy ID appears in the response body. If the public
policies are missing, hydration fails and the pod exits
non-zero before any `/v1/is_authorized` POST runs.

**Expected IDs include the public policies:**
`expected_policy_ids_json()` derives the expected IDs from
the full `policies.json` bundle, mapping each `id` to
`policy/cedar/channels/local/services/server-manager-api/generated/policies/<id>.cedar`.
The bundle (`policies.json:11-17`) contains
`public-intake-allow` and `public-intake-no-read`, so both
public policy IDs are in the hydration gate. Hydration
cannot pass unless OPAL confirms both public policies are
loaded.

**Probe ordering locked in proposal §3:**

> - Post both payloads to `http://opal-client:8180/v1/is_authorized`
>   in the existing proof pod **after initial policy hydration**.
> - **Repeat both posts after the existing polling-interval
>   sleep and second policy hydration check.**

This matches the existing User-allow/User-deny pattern
(`wait_for_policy_ids` → first probes → `sleep 31` →
`wait_for_policy_ids` → second probes), so public probes
inherit the same race-free posture.

**Bootstrap-rejection coverage:** if a future
OPAL/Cedar release rejects a policy that contains the
`Public::` principal type at load time, the policy
ID(s) never appear in `/v1/policies`,
`wait_for_policy_ids` exits non-zero with the existing
"missing policy IDs:%s from
http://opal-client:8180/v1/policies\nlast policies: %s"
message, and the public probes never run. That is the
correct fail-fast posture: a hydration failure is
distinguishable from a decision failure.

**Decision-time coverage:** if the bundle hydrates but
`/v1/is_authorized` rejects the `Public::` principal at
decision time, the curl exits non-zero or returns a body
without `.decision == "Allow"`/`"Deny"`, which the
proposal-locked jq checks (`.decision == "Allow"` /
`.decision == "Deny"`) catch.

**Verdict:** Hydration gate is the existing
`wait_for_policy_ids` function, runs first, and is the
authoritative sequencing gate. No race window between
hydration and probe execution. Audit risk LOW for A2.

## A3 — Failure messages name the principal/action/resource pair

**Locked failure wording (proposal §2 Q3):**

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public, got: <body>
Cedar public read runtime probe expected Deny for Public::"web-intake.local" api:read, got: <body>
```

**Coverage:**

- **Principal:** named in full (`Public::"web-intake.local"`),
  including the entity literal escaping.
- **Action:** named (`application:submit_public` / `api:read`)
  but without the `Action::"..."` Cedar wrapper. An operator
  with the bundle in hand can map the bare action to the
  Cedar `Action` reference unambiguously, since each action
  appears in exactly one policy.
- **Resource:** **NOT** named in either failure message.
  The submit probe's resource is
  `Resource::"server-manager-api:public-applications"` and
  the read probe's resource is
  `Resource::"server-manager-api"`; an operator reading the
  failure message has to consult the validator script (or
  the proposal) to learn which resource the probe asked
  about.
- **Body:** the OPAL response body is included verbatim in
  both messages, which contains principal, action, resource,
  and decision in OPAL's response shape. So the missing
  resource is recoverable from `<body>`, just less
  immediate than if the message named it directly.

**Cardinality wording (proposal §2 Q3):**

```text
expected exactly one Cedar public submit Allow log line, found <n>
expected exactly one Cedar public read Deny log line, found <n>
```

These name the probe but not the principal/action/resource —
acceptable because cardinality drift is a script-shape
concern (extra/missing log line), not a decision-content
concern.

**Hydration-failure wording (existing, unchanged):** if
hydration fails, the existing `missing policy IDs:%s ...`
path covers bootstrap rejection of public policies. The new
probe wording is for post-hydration decision failures only.

**Verdict:** Principal and action are explicit;
resource is recoverable from the response body but not
named directly in the failure message. F2 below on
including the resource in the failure message for
single-line operator debug.

## A4 — Pytest guard reads the validator's payloads (catches drift, not just substring)

**Locked guard (proposal §2 Q2):**

> The pytest guard should assert exact validator content for:
>
> - `Public::\"web-intake.local\"`;
> - `Action::\"application:submit_public\"`;
> - `Resource::\"server-manager-api:public-applications\"`;
> - the public read-deny payload using `Action::\"api:read\"`
>   and `Resource::\"server-manager-api\"`.

And §3:

> Replace the existing assertion that the validator omits
> `application:submit_public` and `web-intake.local` with
> a guard that asserts the validator contains the two live
> public probe payloads.

**Drift class the guard catches:**

1. **Removal.** If a future PR deletes one of the public
   probe payloads from the validator, every required
   substring disappears and the assertion fails. Strong.
2. **Variable rename.** If the implementer renames
   `public_submit_allow_payload` to `public_intake_allow`,
   the substring assertions still pass because they match
   only the JSON content, not the variable name. Acceptable
   — the variable name is internal.
3. **Comment-only retention.** If the validator inadvertently
   carries the payload string in a comment but never wires
   it into a curl invocation, the substring match still
   passes. The probe never runs but the guard is silent.
   This is the canonical "false-pass" scenario the audit
   item is asking about.
4. **Decision wiring drift.** If someone removes the
   `.decision == "Allow"` jq check but leaves the payload
   string and curl invocation in place, the substring
   guard still passes. The probe runs but no longer asserts
   the expected decision; the validator becomes a smoke
   test rather than a contract test.

**The proposal's mitigation:** §2 Q2 says "exact validator
content" but exact-substring-match in pytest is not the
same as parsing the validator's payload structure. A
stronger guard would extract the JSON payloads from the
validator's `jq -nc` invocations and compare them as parsed
objects, OR compile a list of `<probe_name>=...` log lines
the validator emits and assert each public probe has both a
log line and a `.decision == "<expected>"` jq check. The
proposal locks the weaker substring shape, which closes
"removal" drift but not "comment-only retention" or
"decision-wiring drift."

**The existing analog:** the current static guard
(`test_public_intake_policy_fixture.py:101-113`) is also a
substring guard on the validator, asserting the validator
does *not* contain certain strings. The proposal inverts
the polarity (must-contain instead of must-not-contain) but
keeps the same shape. The audit item's bar — "actually
catches drift, not just substring-matches" — is asking for
something stronger than the existing pattern.

**Verdict:** Guard catches removal but not subtler drift
(comment-only retention, decision-wiring drift). F3 below
on parsing-based assertions.

## A5 — No false-positive scenarios (OPAL eventually consistent, Cedar caching, etc.)

**Eventual-consistency surface 1 — hydration not yet
complete:** addressed by `wait_for_policy_ids` (120s
budget) running before each probe round. Probes cannot
execute until OPAL reports every expected policy ID is
loaded.

**Eventual-consistency surface 2 — policy IDs reported
loaded but Cedar engine has not yet recompiled:** the
existing User-allow/User-deny probes run through the same
sequence and have not exhibited this kind of false positive
in the established access-policy lane. OPAL reports
`/v1/policies` from its own internal store, which is
populated only after the Cedar engine accepts the bundle;
the engine acceptance is what drives the report. So a
"hydrated but not enforceable" window does not exist by
construction.

**Eventual-consistency surface 3 — OPAL polling reload
mid-probe:** the validator already runs a second probe
round after `sleep 31` (one polling interval) and a second
`wait_for_policy_ids`. Adding the public probes to both
rounds means a transient mid-poll state cannot pass round 1
and fail round 2 (or vice versa) without surfacing.

**Cedar decision caching:** Cedar evaluates each
authorization request against the loaded policy set without
caching by request hash. There is no per-(principal,
action, resource) cache that could return a stale Allow/Deny
across a policy reload. Even if such a cache existed, the
two-round probe pattern would catch divergence between the
cached and reloaded decisions.

**Network jitter / curl retry behavior:** the existing
`curl -fsS -X POST ...` posture exits non-zero on any HTTP
4xx/5xx, transit failure, or partial response. A transient
network failure surfaces as a non-zero curl exit, which the
proof script's `set -e` propagates as pod failure. The
public probes inherit this. Not a false positive — a true
hydration/transport failure.

**Body-decoding races:** the proposal locks
`jq -e '.decision == "Allow"' <<<"${allowed_body#prefix=}"`
checks identical to the existing pattern. If OPAL returns a
malformed body (extremely unlikely once hydration is
complete), the jq check fails with the locked failure
message. Not a false positive.

**Schema enforcement asymmetry across rounds:** the
hypothetical BL-012 risk is that future OPAL/Cedar starts
rejecting `Public::` principal types. If that rejection is
deterministic given the bundle, both rounds fail the same
way and the test correctly fails. If the rejection is
flaky (e.g., schema validator only runs on first request
after a reload), one round passes and the other fails — the
two-round structure catches this. Either way, no false
positive.

**Channel-mismatch race:** the validator dies if
`channel != "local"` (line 106) before any probe runs, so
the local-only probe payload cannot run against a non-local
hydrated bundle.

**Verdict:** No identified false-positive scenarios. The
two-round structure plus hydration gate is the correct
posture for OPAL/Cedar's eventual-consistency surface.
Audit risk LOW for A5.

## Findings

### F1 — Read-deny probe action/resource diverge from `authorize_public_intake`

**Severity:** low (audit-criterion alignment, not behavior).

**Where:** the read-deny probe in
`infra/tests/validate_access_policy_local.sh` (proposal §3).

**Risk:** the audit gate item reads "the two new probes
target the EXACT principals/actions/resources used by
`authorize_public_intake`." The submit-allow probe is an
exact match. The read-deny probe targets the same
`Public::` principal but a different action (`api:read`)
and resource (`server-manager-api`) than
`authorize_public_intake` ever issues. This is intentional
under the proposal — the second probe is the matching
forbid statement in the bundle, included so a Cedar runtime
that accepts `Public::` for one action but rejects it for
another is detected. But strictly read, only one of the
two probes is a production-call reproduction.

**Action:** treat as an audit-criterion clarification, not
a behavior gap. Either (a) document in the proposal that
the read-deny probe deliberately exercises a different
action to cover the matching forbid policy and is not a
reproduction of `authorize_public_intake`'s call, or (b)
swap the read-deny probe for a second submit-action probe
under a non-public principal (e.g., `User::"sample"` for
`application:submit_public`) that should fall through to
implicit deny. Option (a) is closer to the proposal's
intent (catching `Public::` principal-type rejection at
both allow and forbid sites) and should be accepted as
locked.

### F2 — Failure message omits the resource literal

**Severity:** low (operator-debuggability).

**Where:** `validate_access_policy_local.sh` failure
strings for the public probes (proposal §2 Q3).

**Risk:** the locked failure wording names principal and
action but not resource. A first-pass operator reading the
CI failure sees:

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public, got: <body>
```

…and has to read `<body>` (or open the validator script) to
recover that the probe asked about
`Resource::"server-manager-api:public-applications"`. In
the local bundle this is unambiguous because each
action/resource pair is unique, but the message is less
debug-friendly than naming the full triple.

**Action:** extend the locked wording to include the
resource literal:

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public on Resource::"server-manager-api:public-applications", got: <body>
Cedar public read runtime probe expected Deny for Public::"web-intake.local" api:read on Resource::"server-manager-api", got: <body>
```

Cost is one additional substring per failure path. No
script-flow change.

### F3 — Pytest guard is substring-shaped, not parsed-payload-shaped

**Severity:** medium-low (drift detection completeness).

**Where:** `infra/tests/test_public_intake_policy_fixture.py`
or `infra/tests/test_validate_access_policy_local_probes.py`
(proposal §3 alternate file).

**Risk:** the audit gate item reads "Pytest guard reads the
validator's payloads — actually catches drift, not just
substring-matches." The locked guard (proposal §2 Q2) is a
must-contain-substring assertion for each of the four
required Cedar literals. This catches:

- removal of either probe payload from the validator;
- character-level drift in the principal/action/resource
  literals.

It does not catch:

- a payload that is present in a comment or in a removed-
  but-not-deleted code block, never wired into a curl
  invocation;
- removal of the matching `.decision == "Allow"` /
  `.decision == "Deny"` jq check while the payload string
  remains;
- a payload that is built but never POSTed to
  `/v1/is_authorized`;
- a payload whose log-line prefix was renamed such that the
  cardinality assertion becomes vacuous.

**Action:** strengthen the guard to parse the validator
script and assert structural properties, not just string
presence. Two reasonable shapes:

- **(a) Payload-parse guard.** The guard regex-extracts
  every `jq -nc '{...}'` payload definition in the
  validator, parses each into a dict, and asserts that the
  set of payloads contains exactly the four expected
  triples (User allow, User deny, Public submit allow,
  Public read deny). Catches comment-only retention and
  payload-without-curl-wiring drift because the
  extracted set comes from actual `jq` invocations.
- **(b) Probe-wiring guard.** The guard asserts, for each
  expected probe, that the validator contains all of: a
  payload variable assignment, a `printf "<probe>=..."`
  log line, an `--env="<PROBE>_PAYLOAD=..."` pod env, a
  `curl ... --data-binary @-` POST, a cardinality assertion
  on the probe's log prefix, and a `.decision == "<expected>"`
  jq check on the probe's body. Catches all four drift
  classes above.

Option (a) is the lighter change; option (b) is the
stronger guard. Either keeps the BL-012 lock from silently
weakening over time. The proposal's diff budget (≤35 lines
of pytest churn) accommodates either.

### F4 — Second-round probe `.decision` check not explicitly locked

**Severity:** low (defense-in-depth completeness).

**Where:** `validate_access_policy_local.sh` second probe
round (proposal §3).

**Risk:** the existing User probes run twice (before/after
`sleep 31`) with `allow=`/`deny=` and `allow_after_poll=`/
`deny_after_poll=` log lines, but only the first-round
lines are asserted with `jq -e '.decision == "..."'`. The
second-round bodies are printed but not jq-checked. The
proposal §3 says "Assert `.decision == "Allow"` for public
submit and `.decision == "Deny"` for public read" without
specifying first vs. second round.

If the implementation follows the existing pattern, the
second-round public probe bodies will be printed but not
asserted. A scenario where round 1 passes and round 2
silently returns a wrong decision would not fail the test
unless the cardinality of the log lines also changes.

**Action:** lock the implementation to assert
`.decision == "Allow"` / `.decision == "Deny"` on **both**
rounds for the public probes, OR document that the
second-round probe is informational (and accept the gap as
a continuation of the existing User-probe pattern). The
former closes the gap with negligible script churn (two
extra jq-e calls). The latter accepts that round-2
divergence is caught only via cardinality, which is weaker.

This finding is forward-looking — the proposal does not
preclude either choice, but the implementation PR should
lock one explicitly.

## Verdict reasoning

BL-012 holds the audit gate at LOW risk:

- **Probe triples (A1):** submit-allow probe exactly matches
  the `Public::"web-intake.local"` /
  `Action::"application:submit_public"` /
  `Resource::"server-manager-api:public-applications"`
  triple constructed by `authorize_public_intake`. Read-deny
  probe targets the same `Public::` principal against the
  matching forbid statement in `policies.json`; this
  diverges from `authorize_public_intake`'s actual call but
  is the right second probe for BL-012's
  principal-type-acceptance scope. F1 captures the
  audit-criterion clarification.
- **Hydration ordering (A2):** the existing
  `wait_for_policy_ids` function gates every probe round and
  is the authoritative race-free sequencing primitive. The
  expected policy IDs derived from `policies.json` include
  `public-intake-allow` and `public-intake-no-read`, so
  bootstrap rejection of the public policies fails the
  hydration gate before any probe runs.
- **Failure messages (A3):** principal and action are named
  explicitly; resource is recoverable from the response body
  but not named in the failure message itself. F2 captures
  the operator-debuggability gap and the trivial fix.
- **Pytest guard (A4):** the locked substring-match guard
  catches probe-removal drift but not subtler drift
  (comment-only retention, decision-check drift,
  payload-without-curl-wiring). F3 captures the
  parsing-based strengthening.
- **False-positive surface (A5):** the two-round probe
  structure plus 120-second hydration polling is robust
  against OPAL eventual consistency, Cedar engine recompile
  windows, polling reload mid-probe, and per-request
  caching. No identified false-positive scenarios. F4
  captures the second-round `.decision` check as
  defense-in-depth completeness.

None of the findings block BL-012 from landing as locked.
F1 is a documentation alignment, F2 is a one-line wording
fix, F3 is the only finding with non-trivial implementation
weight (and is itself a strengthening of the locked guard,
not a behavior change), and F4 is a small implementation
choice that should be made explicit in the implementation
PR.

Verdict: LOW.

AUDIT_DONE: plans/risk/bl-012-audit.md
