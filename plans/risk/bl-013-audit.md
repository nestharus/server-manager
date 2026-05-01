# BL-013 — Audit risk gate

**Verdict:** LOW

Scope: BL-013 — add `infra/tests/test_public_intake_channel_tripwire.py`,
a static CI tripwire that walks non-local `gitops/channels/<channel>/`
directories, detects whether a channel ships public-intake-relevant
server-manager application manifests, and — once triggered — asserts
the full four-item public-intake substrate group is materialized for
that same channel with channel-derived hostnames and channel-derived
public principal. The slice is test-only: no production code, no
GitOps manifest changes, no Cedar bundle changes.

The audit gate inspects: (1) trigger condition is precise (presence
of public-intake-relevant manifests, not directory existence);
(2) all four substrate items are checked (API rate-limit YAML,
Pomerium rate-limit YAML, Cedar policy, Pomerium route coverage);
(3) the channel public principal is channel-derived rather than
hardcoded to `web-intake.local`; (4) failure messages name the
channel and the missing/invalid item; (5) existing channels (just
`local` today) pass — including absent `gitops/channels/dev/` and
the cedar-only `policy/cedar/channels/dev/`; (6) the synthetic-fixture
negative test actually fires the tripwire.

Source proposal: `proposals/32-bl-013-channel-tripwire.md`.
Source problem map: `research/47-bl-013-tripwire-problem-map.md`.
Existing local tests (reference style): `infra/tests/test_public_intake_rate_limit.py`.

## Repository facts cross-checked

- `gitops/channels/` contains exactly one channel directory: `local`.
  No `gitops/channels/dev/` exists.
- `policy/cedar/channels/` contains `local` and `dev`. The `dev`
  cedar directory exists in isolation from any `gitops/channels/dev/`
  workload materialization — exactly the false-trigger trap the
  proposal locks against in Q1.
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  contains `KongPlugin/public-intake-rate-limit` (namespace
  `server-manager`, `policy: local`) and
  `Ingress/server-manager-public-intake-api` annotated
  `konghq.com/plugins: public-intake-rate-limit` exposing
  `/api/v1/public/applications` and `/api/v1/public/chapters` as
  `Prefix` routes to `server-manager-api:8000` on
  `api.local.humility.local`. Matches the proposal's Q2 item 1
  exactly.
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  contains `Ingress/web-public-intake` (namespace `auth-system`,
  same plugin annotation) exposing `/api/public/applications`,
  `/api/public/chapters`, `/api/applications` as `Prefix` routes to
  `pomerium-proxy:80` on `web.local.humility.local`. Matches Q2
  item 2 exactly.
- `policy/cedar/channels/local/services/server-manager-api/policies.json`
  contains `public-intake-allow` (permitting
  `Public::"web-intake.local"` →
  `Action::"application:submit_public"` on
  `Resource::"server-manager-api:public-applications"`) and
  `public-intake-no-read` (forbidding the same principal from
  `Action::"api:read"` on `Resource::"server-manager-api"`). Matches
  Q2 item 3 and Q3's principal pattern.
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
  has the rendered `pomerium-config` route block with multiple
  `from: https://web.local.humility.local` routes; the public web
  route uses `to: http://server-manager-web.web.svc.cluster.local:8080`
  with `allow_public_unauthenticated_access: true`, and identity-
  bearing routes for the same web host precede the public catch-all.
  Matches Q2 item 4.

The proposal's substrate facts about the current repository are all
accurate. The reference style helpers from
`test_public_intake_rate_limit.py` (`_yaml_documents`,
`_metadata`, `_annotations`) carry over cleanly.

## A1 — Trigger condition is precise

**Lock (Q1):** "For every non-local directory under
`gitops/channels/`, inspect
`gitops/channels/<channel>/applications/server-manager/` if it
exists. The tripwire is armed for that channel when the directory
contains non-empty YAML that signals public intake in any of these
ways."

Four trigger signals are enumerated:

1. An `Ingress` host/path exposing `/api/v1/public/applications`,
   `/api/v1/public/chapters`, `/api/public/applications`,
   `/api/public/chapters`, or `/api/applications`.
2. A YAML file named `public-intake-rate-limit.yaml`.
3. A resource named `server-manager-public-intake-api`,
   `web-public-intake`, or `public-intake-rate-limit`.
4. A `Kustomization` resource entry that includes
   `public-intake-rate-limit.yaml`.

These are the same four signals enumerated in the problem map's
Option B (lines 138–149), unchanged.

**Two false-trigger traps explicitly disarmed:**

- Absence of `gitops/channels/dev/` is valid — the test walks only
  existing directories.
- Existence of `policy/cedar/channels/dev/` is *not* a trigger —
  the trigger lives under `gitops/channels/<channel>/applications/
  server-manager/`, not under cedar.

**Coverage of trigger signal redundancy:** signal 1 (path-level)
catches manifests that ship public-intake routes without using the
canonical filename. Signal 2 (filename) catches resources that ship
the canonical file with non-canonical content. Signal 3 (resource
name) catches resource splits across non-canonical filenames.
Signal 4 (kustomization include) catches the case where the
canonical file is referenced by kustomization but not yet written
or only written as a placeholder. The four signals are
defense-in-depth: any one ought to be enough, but the union
catches drift from any single naming or layout convention.

**Verdict:** Trigger condition is precise — both in the affirmative
sense (four redundant signals catch any reasonable form of
public-intake materialization) and in the negative sense (absent
GitOps directories and cedar-only directories explicitly do not
trigger). Audit risk LOW for A1.

## A2 — All four substrate items are checked

**Lock (Q2):** four items, each with explicit content requirements:

1. `gitops/channels/<channel>/applications/server-manager/
   public-intake-rate-limit.yaml` — must exist; must contain
   `KongPlugin/public-intake-rate-limit` and
   `Ingress/server-manager-public-intake-api`; ingress must use
   `konghq.com/plugins: public-intake-rate-limit`; must expose
   `/api/v1/public/applications` and `/api/v1/public/chapters` as
   path-specific `Prefix` routes to `server-manager-api:8000`.
2. `gitops/channels/<channel>/auth/pomerium/
   public-intake-rate-limit.yaml` — must exist; must contain
   `Ingress/web-public-intake` with the same plugin annotation;
   must expose `/api/public/applications`, `/api/public/chapters`,
   `/api/applications` as path-specific `Prefix` routes to
   `pomerium-proxy:80`.
3. `policy/cedar/channels/<channel>/services/server-manager-api/
   policies.json` — must exist; must include `public-intake-allow`
   (permit the channel public principal on
   `Action::"application:submit_public"` on
   `Resource::"server-manager-api:public-applications"`) and
   `public-intake-no-read` (forbid the same principal from
   `Action::"api:read"` on `Resource::"server-manager-api"`).
4. `gitops/channels/<channel>/auth/pomerium/
   secrets-infisicalsecret.yaml` — must exist; rendered
   `pomerium-config` `config.yaml` must include web-host routing to
   `server-manager-web.web.svc.cluster.local:8080` with
   `allow_public_unauthenticated_access: true`; identity-bearing
   web/API routes for the same web host must remain explicit and
   ordered before the public catch-all.

This is a 1:1 match against the four-item substrate group named in
the problem map (lines 75–82). No item is dropped; no item is
collapsed into another.

**Hostname-derivation lock:** the proposal explicitly requires
non-local channels to use `api.<channel>.humility.gg` and
`web.<channel>.humility.gg` and to reject local hostnames in
non-local substrate. This is the second-order "drift via copy-paste"
failure mode beyond plain absence — and it is locked in Q2 §99–103.
However, see F2: the hostname-rejection lock has no explicit test
acceptance criterion in TG-2 or TG-3.

**Pomerium route ordering check:** item 4 requires not just the
public route's existence but also that "identity-bearing web/API
routes for the same web host must remain explicit and ordered
before the public catch-all so protected paths are not shadowed."
This is a structural list-order assertion (walk the routes list
in order, identify the public catch-all index, verify identity-
bearing routes have lower indices). It is non-trivial in a
`yaml.safe_load`-then-`isinstance` style. The 180–260 LOC budget
absorbs this if the implementation reuses the helper pattern from
existing tests, but it is the heaviest single check in the slice.

**Verdict:** All four substrate items are explicitly enumerated
with content-level requirements that match the local reference
shape. Hostname-derivation is locked at the proposal level (F2
flags the missing TG acceptance). Audit risk LOW for A2.

## A3 — Channel principal name is channel-derived

**Lock (Q3):** `Public::"web-intake.<channel>"`, with the explicit
prohibition: "The test must not hard-code `Public::"web-intake.local"`
as acceptable for non-local channels. For example, a future `dev`
channel must require `Public::"web-intake.dev"` in both the submit
permit and read forbid policies."

**Verification path against current local substrate:** in
`policy/cedar/channels/local/services/server-manager-api/policies.json`,
both `public-intake-allow` and `public-intake-no-read` use
`Public::"web-intake.local"` literally. A naive implementation that
reused the local content via copy/paste for a future `dev` channel
would carry `web-intake.local` forward — and the proposal's lock
explicitly rejects that. The test must derive the expected principal
from the channel directory name and assert against that derived
value, not against a hardcoded constant.

**Two assertion sites:** the principal must match in both
`public-intake-allow` (permit) and `public-intake-no-read`
(forbid) entries. The proposal enumerates both, closing the
asymmetric-drift case where one entry uses
`web-intake.<channel>` and the other still uses
`web-intake.local`.

**TG-3 acceptance:** "the fixture proves the test is
channel-derived and does not rely on `web-intake.local` or local
hostnames." This is the positive proof that the test fails closed
when given a channel-derived fixture — i.e., the test does not
silently accept `web-intake.local` because of a hardcoded fallback.

**Verdict:** The channel principal is locked as channel-derived
in both the proposal and TG-3. Audit risk LOW for A3.

## A4 — Failure messages name channel + missing item

**Lock (Q4):**

```text
public-intake channel tripwire failed for <channel>: missing <item>
public-intake channel tripwire failed for <channel>: invalid <item>: <detail>
```

Aggregation requirement: "When several group members are missing,
aggregate them into one assertion for the channel so CI explains
the incomplete substrate in one run."

**Two message shapes:** missing-item ("file/resource absent") and
invalid-item ("file/resource present but content drifted"). The
two shapes correspond to the two failure modes of partial
materialization: omission and corruption. Both are needed.

**TG-2 acceptance:** "the failure text names the fake channel and
every missing item, using the format locked in Q4." This locks
the message format and the aggregation requirement at test-level.

**Aggregation versus first-failure:** by requiring aggregation,
the proposal avoids the iterative-CI trap where a developer fixes
one missing item, runs CI again, sees the second missing item,
fixes that, runs CI again, etc. One run lists every gap. This is
the right shape for a tripwire whose purpose is to surface
incomplete-substrate state in one read.

**Verdict:** Both message shapes and the aggregation requirement
are locked in Q4 and reinforced in TG-2 acceptance. Audit risk
LOW for A4.

## A5 — Existing channels (just `local`) pass

**Lock (TG-1 acceptance):**

- `local` is skipped as the reference channel already covered by
  local tests.
- Absent `gitops/channels/dev/` does not fail.
- Existing `policy/cedar/channels/dev/` does not trigger the
  tripwire by itself.
- If no non-local channel contains public-intake-relevant
  `applications/server-manager` manifests, the repository-state
  test passes.

**Three-fold pass condition:** the test passes today because (a)
no channel matches the iteration scope (only `local` exists, and
local is excluded); (b) no `gitops/channels/dev/` directory exists,
so the iteration finds nothing; (c) the cedar-only `dev` directory
is not part of the iteration scope.

**Why "skip local" is the correct choice:** the tripwire's purpose
is to catch cross-channel partial materialization, not to validate
the reference local substrate. Local already has dedicated coverage
in `test_public_intake_rate_limit.py` (the same file BL-014 is
extending in a parallel slice). Re-asserting the local invariants
in this new test would duplicate coverage and create maintenance
ambiguity about which test "owns" the local invariants. Skipping
local is the right separation of concerns.

**Verdict:** Existing-channel pass condition is correctly defined
and matches today's repository state on all three axes. Audit risk
LOW for A5.

## A6 — Synthetic-fixture negative test fires the tripwire

**Lock (TG-2):** synthesize a fake non-local channel under
`tmp_path` with public-intake-relevant `applications/server-manager`
material and only part of the substrate group.

Acceptance:

- the tripwire detects the fake channel as public-intake-relevant
  (proves the trigger logic actually fires);
- the assertion fails (proves the substrate-completeness check
  actually rejects);
- the failure text names the fake channel and every missing item,
  using the format locked in Q4 (proves the message contract).

**Symmetric positive test (TG-3):** synthesize a complete fake
channel and assert the tripwire passes. This is the inverse of
TG-2 and proves the test does not fail vacuously (i.e., it can
also accept).

**Why the fixture pair is the right shape:**

- TG-2 alone could pass even if the trigger never fires — a vacuous
  assertion failure on the channel-name scaffold. By requiring
  TG-3 to pass with full substrate, the proposal proves the
  tripwire's *positive* state is reachable, which means TG-2's
  failure was caused by missing substrate, not by an always-failing
  test.
- TG-3 alone could pass even if the trigger never fires (vacuous
  pass — the channel was detected as non-public-intake and skipped).
  TG-2 closes that loop by requiring detection.
- The two tests together prove both halves of the trigger contract:
  detection works, and detection's downstream substrate check works.

**Helper reusability:** the proposal §3 says "Provide fixture
helpers that can run the same tripwire logic against a temporary
synthetic channel root for negative and positive tests." This is
the right factoring — the same enumeration/assertion code path
is exercised by repository-state, TG-2, and TG-3. Without this
factoring, the synthetic tests would test a parallel implementation
and not the real one.

**Verdict:** TG-2 explicitly fires the tripwire and asserts on the
locked message format; TG-3 proves the inverse case; the helper
factoring ensures both tests exercise the production code path.
Audit risk LOW for A6.

## Findings

### F1 — TG-2 does not explicitly cover the aggregation case

**Severity:** medium-low (completeness; aggregation contract is
locked but not test-enforced).

**Where:** TG-2 acceptance, proposal §4.

**Risk:** Q4 mandates aggregation: "When several group members are
missing, aggregate them into one assertion for the channel so CI
explains the incomplete substrate in one run." TG-2 says "the
failure text names the fake channel and every missing item, using
the format locked in Q4." The phrase "every missing item" implies
the test fixture has multiple missing items, but the proposal does
not explicitly require TG-2 to exercise *both* a single-missing
case (aggregation == 1 item) and a multi-missing case (aggregation
> 1 items).

A naive implementation could pass TG-2 with only one item missing
in the fixture. That would not exercise the aggregation
concatenation logic. If a developer later changes the assertion
format to a fail-fast first-error style (regression), TG-2 would
still pass with a single-item fixture — and the aggregation
contract from Q4 would silently break.

**Action:** sharpen TG-2 acceptance to explicitly require the
fixture omit at least two of the four substrate items, and assert
that the failure message contains both omitted item names. Or
split TG-2 into TG-2a (single-missing) and TG-2b (multi-missing).
Cost: one extra fixture variant in the test file.

### F2 — Hostname-rejection lock has no test acceptance criterion

**Severity:** medium (correctness; second-order drift not test-enforced).

**Where:** Q2 §99–103 (hostname rejection requirement), TG-3
acceptance.

**Risk:** Q2 explicitly says "the tripwire should reject local-only
hosts such as `api.local.humility.local` or `web.local.humility.local`
in non-local substrate. The expected remote hostname pattern for
this check is `api.<channel>.humility.gg` and
`web.<channel>.humility.gg`." This is a real failure mode: a
copy-paste from the local channel into a future `dev` channel
would carry `api.local.humility.local` forward into the dev
substrate, and the tripwire is supposed to catch that.

TG-3 says "the fixture proves the test is channel-derived and does
not rely on `web-intake.local` or local hostnames" — this is the
positive proof that channel-derived hostnames are accepted. TG-2
says the fixture is missing items — it does not exercise the
hostname-drift case where items are present but use local
hostnames.

There is no test that synthesizes a fake non-local channel with
*all four substrate items present* but using `api.local.humility.local`
or `web.local.humility.local` and asserts the tripwire rejects
with the "invalid <item>: <detail>" message shape from Q4. Without
this test, the hostname rejection logic is locked in the proposal
but not test-enforced — a future implementer could omit it
entirely and TG-1, TG-2, TG-3 would all pass.

**Action:** add a TG-4 acceptance criterion (or extend TG-2)
requiring a fake channel with full-but-host-drifted substrate
that triggers the "invalid" failure shape. The fixture would be
TG-3 minus the channel-derived hostnames plus
`api.local.humility.local`. The test asserts the failure message
contains "invalid <hostname-bearing-item>: <local-host-detail>".
Cost: one extra fixture variant; reuses TG-3's full-substrate
helper.

The same rationale applies to the channel public principal: a fake
channel with `Public::"web-intake.local"` instead of
`Public::"web-intake.<channel>"` should trigger an invalid-item
failure. TG-3 implies this is rejected (by accepting the
channel-derived form), but a dedicated negative case would be
cheaper to read in CI.

### F3 — Pomerium route ordering check is non-trivial; budget tight

**Severity:** low (implementation density observation; not a
proposal defect).

**Where:** Q2 item 4, "Identity-bearing web/API routes for the
same web host must remain explicit and ordered before the public
catch-all so protected paths are not shadowed."

**Risk:** the route-ordering check is the heaviest single
assertion in the slice. It requires:

- Loading `secrets-infisicalsecret.yaml`.
- Extracting the `pomerium-config` field's nested rendered
  YAML string and re-parsing it.
- Walking the `routes:` list in order.
- Identifying the public catch-all route (the route with
  `allow_public_unauthenticated_access: true` and the most
  permissive path/prefix).
- Identifying identity-bearing routes (routes for the same `from`
  host without `allow_public_unauthenticated_access: true`, or
  with explicit auth-bearing settings).
- Asserting all identity-bearing routes have lower list indices
  than the public catch-all.

The 180–260 LOC budget can absorb this if the implementation reuses
existing helpers, but a naive re-parse of nested rendered YAML
plus list-order walking can easily consume 60–80 LOC for this one
check alone. If the implementation runs over budget, the most
likely sacrifice is the route-ordering check — which is the
substantive shadowing-defense check in item 4. Without it, item 4
collapses to "public catch-all exists" which is the weaker form
the proposal explicitly rejects.

**Action:** during implementation, prioritize the route-ordering
check inside item 4. If budget pressure forces a trim, trim the
hostname pattern check (F2's territory) before trimming the
ordering check. Or, factor the route-ordering helper into
`infra/tests/_pomerium_routes.py` (or similar) so subsequent
slices can reuse it without re-implementing.

### F4 — TG-1 acceptance is silent on what "skipped" means at the assertion level

**Severity:** very low (clarity; not a defect).

**Where:** TG-1 acceptance, "`local` is skipped as the reference
channel already covered by local tests."

**Risk:** "skipped" can mean two things at the test-implementation
level: (a) the iteration excludes `local` from the channel list
before any assertion runs, or (b) the iteration includes `local`
but the per-channel checks short-circuit on a `channel == 'local'`
guard. Both produce the same TG-1 outcome (local does not fail
the test), but they have different drift sensitivities:

- Form (a) — exclusion at iteration — is simpler and harder to
  bypass.
- Form (b) — guard-based skip — could mask a future `local`-channel
  drift if the guard fires before the substrate check.

The proposal does not lock which form is used. This is a minor
implementation-clarity question, not a correctness defect, but
form (a) is the cleaner choice and worth naming.

**Action:** clarify in the implementation that `local` is excluded
at the iteration filter (form a), not via a per-channel guard
(form b). The test should walk
`[d for d in (REPO_ROOT / "gitops/channels").iterdir() if d.is_dir() and d.name != "local"]`
or equivalent. No proposal change needed; this is a code-style
note for the implementer.

## Verdict reasoning

BL-013 holds the audit gate at LOW risk:

- **Trigger precision (A1):** Q1 locks four redundant trigger
  signals (path patterns, filename, resource names, kustomization
  includes) and explicitly disarms two false-trigger traps
  (absent GitOps directory, cedar-only directory). All four
  signals match the problem map's Option B exactly.
- **Substrate coverage (A2):** Q2 enumerates all four items with
  content-level requirements that match the local reference
  exactly: API rate-limit YAML, Pomerium rate-limit YAML, Cedar
  policy file, Pomerium routes in `secrets-infisicalsecret.yaml`.
  Hostname-derivation is locked at the proposal level (F2 flags
  the missing TG acceptance for this).
- **Channel-derived principal (A3):** Q3 locks
  `Public::"web-intake.<channel>"` for both `public-intake-allow`
  and `public-intake-no-read`, and TG-3 explicitly proves the
  test is channel-derived rather than hardcoded to
  `web-intake.local`.
- **Failure messaging (A4):** Q4 locks both message shapes
  (missing/invalid) and the aggregation requirement; TG-2 enforces
  the message format. F1 flags that TG-2 should explicitly cover
  the multi-missing aggregation case.
- **Existing channels pass (A5):** TG-1 acceptance covers all three
  axes of today's repo state — `local` skipped, absent
  `gitops/channels/dev/`, cedar-only `dev` does not trigger.
- **Synthetic negative test (A6):** TG-2 and TG-3 form a
  symmetric pair (negative and positive) sharing helper code, so
  both halves of the trigger contract are exercised against the
  production code path.

The slice is test-only, ~180–260 LOC, no production code, no
GitOps manifest changes, no Cedar bundle changes, no shell
validator changes. All six gate criteria are met with acceptable
scope and explicit limits. F1 (aggregation case in TG-2) and F2
(hostname-drift negative test) are completeness improvements that
should be folded into the implementation pass. F3 (Pomerium route
ordering) is an implementation-density observation. F4 (skip-form
clarity) is a code-style note.

Verdict: LOW.

AUDIT_DONE: plans/risk/bl-013-audit.md
