# BL-012 — Shortcut risk gate (Public:: runtime probe)

**Verdict:** LOW

Scope: BL-012 — close the runtime gap on the `Public::"web-intake.local"`
Cedar principal. Today, every test that asserts public-intake authorization
operates on policy text or matrix fixtures; no live OPAL/Cedar decision is
exercised for `Public::`. The slice extends
`infra/tests/validate_access_policy_local.sh` with two real HTTP probes
against the in-cluster OPAL client (allow on `application:submit_public`,
deny on `api:read`), runs them before and after the existing
polling-interval recheck, asserts decision and cardinality, and adds a
pytest guard that reads the validator script and asserts both probe
payloads are present.

The shortcut gate inspects whether the slice (1) issues real HTTP probes
to live OPAL rather than re-reading the policy file, (2) probes both an
Allow case and a Deny case rather than only one direction, (3) has a
pytest guard that reads the validator script (not just "trust that the
script does the right thing"), and (4) avoids "TODO: matrix-driven later"
stubs in the validator code.

Source: `proposals/29-bl-012-public-entity-runtime-probe.md`,
`research/42-bl-012-public-entity-problem-map.md`,
`infra/tests/validate_access_policy_local.sh`.

## C1 — Real HTTP probes to live OPAL (not "trust the policy file")

**Pass.**

§3 (Substrate, lines 122-138) of proposal 29 lands the probes inside the
existing in-cluster proof pod — the same pod that today posts the sample
`User::` allow/deny to `http://opal-client:8180/v1/is_authorized`:

> - Add two public payload variables beside the existing `allow_payload`
>   and `deny_payload`.
> - Post both payloads to `http://opal-client:8180/v1/is_authorized` in
>   the existing proof pod after initial policy hydration.
> - Repeat both posts after the existing polling-interval sleep and
>   second policy hydration check.

The validator already runs an `init-115-cedar` pod inside `auth-system`
that `curl`s `/v1/policies` until canonical IDs hydrate, then `curl`s
`/v1/is_authorized` (lines 232-245 of the script). The new public probes
ride that same lane, against the same live OPAL client deployment whose
rollout is awaited at line 187. Q1 (proposal lines 49-52) is explicit
that the probes only run after `/v1/policies` confirms hydration, and
that `--static-only` is not allowed to claim coverage:

> The live probes must run only after `/v1/policies` confirms the
> canonical OPAL policy IDs are hydrated, using the same runtime lane as
> the current access policy validator. `--static-only` remains
> static-only and does not attempt to catch OPAL/Cedar runtime
> behavior.

This is the right layer. The problem map (research/42 lines 80-85)
documents that an OPAL/Cedar release rejecting an unknown principal
type at decision time would be invisible to existing live access tests —
they probe only `User::`. Putting the new probes on `/v1/is_authorized`
with the actual `Public::"web-intake.local"` principal is the only test
shape that catches Cedar decision-boundary rejection of the public
entity type.

The matrix and policy-bundle fixture tests
(`test_public_intake_policy_fixture.py:46-83`) stay; they cover policy
text drift. The new probe is additive coverage at the OPAL decision
boundary.

**Risk:** the natural shortcut would be to (a) keep the new check in the
static layer — assert that `policy/cedar/.../policies.json` contains
the public permit and forbid statements, calling that "runtime
coverage" — or (b) add a probe that hits a fake authorizer instead of
the live OPAL client, so the test would still pass against an OPAL
release that rejects the entity type.

**Mitigation:** the proposal posts to
`http://opal-client:8180/v1/is_authorized` in the cluster's auth-system
namespace, gated on `/v1/policies` hydration of the canonical IDs, in
the same proof pod that already runs the `User::` allow/deny. No
`--static-only` shortcut path; the probes only exist on the runtime
lane.

**Verdict:** Not a shortcut.

## C2 — Both Allow + Deny probes (not just one)

**Pass.**

Q1 (proposal lines 32-43) names two probes, not one:

> - allow `Public::"web-intake.local"` to perform
>   `Action::"application:submit_public"` on
>   `Resource::"server-manager-api:public-applications"`;
> - deny `Public::"web-intake.local"` from performing `Action::"api:read"`
>   on `Resource::"server-manager-api"`.

§3 (lines 132-136) doubles down: the validator must `Assert
.decision == "Allow"` for public submit and `.decision == "Deny"` for
public read, and assert exactly one allow line and one deny line in the
proof pod logs. The probe pair is run twice — before and after the
30-second polling-interval sleep at line 223 of the script — matching
the cadence of the existing `User::` probes.

The Allow side proves the public submit principal is recognized and
permitted for `application:submit_public`. The Deny side proves the
forbid statement is not silently dropped from policy compilation: a
buggy Cedar release that interpreted the public entity as a no-op
(neither allow nor deny) would still pass an Allow-only probe (because
no policy denies `application:submit_public` for that principal in the
bundle), but would fail the Deny probe on `api:read`. Both directions
are needed, and both are present.

The problem map (research/42 lines 99-115) called out exactly this
asymmetry: an Allow-only probe catches "the policy isn't there at all,"
but only a Deny probe catches "the forbid compiles to a default-allow"
or "the principal type evaluates to wildcard." Q4 (proposal lines
105-118) keeps the slice scoped to `Public` (Tenant/User/Service have
their own runtime probes), so the two-probe pair is the full
public-principal coverage delivered here.

**Risk:** the natural shortcut would be (a) probe only the allow side
("public submit returns Allow, we're good"), missing the failure mode
where the forbid statement is silently dropped, or (b) skip the
post-poll re-probe so a transient hydration window passes the test
without proving steady-state behavior.

**Mitigation:** two probes in two directions, run twice (initial
hydration + after a polling-interval sleep), with cardinality
assertions ("exactly one public submit Allow log line, exactly one
public read Deny log line") so a regression that emits zero or
duplicate decisions fails clearly per the failure wording in Q3
(proposal lines 79-103).

**Verdict:** Not a shortcut.

## C3 — Pytest guard reads the script (not "trust me the probes are there")

**Pass.**

Q2 (proposal lines 56-77) locks the guard's substrate: it reads the
validator script and asserts each of the four payload tokens is
present. The required substrings are:

> - `Public::\"web-intake.local\"`;
> - `Action::\"application:submit_public\"`;
> - `Resource::\"server-manager-api:public-applications\"`;
> - the public read-deny payload using `Action::\"api:read\"` and
>   `Resource::\"server-manager-api\"`.

§3 (Substrate, lines 136-148) names the file:
`infra/tests/test_public_intake_policy_fixture.py`. The guard
**replaces** the existing assertion that the validator omits
`application:submit_public` and `web-intake.local`:

> Replace the existing assertion that the validator omits
> `application:submit_public` and `web-intake.local` with a guard that
> asserts the validator contains the two live public probe payloads.

The replacement is binding: today the static guard at
`test_public_intake_policy_fixture.py:101-113` actively rejects the
strings the new validator must contain (per problem map lines 41-42).
Without this flip, adding the probes to the script would break the
existing test, so the guard cannot be silently dropped — it has to be
updated, and once updated it asserts the probes' presence.

The acceptable alternate (proposal lines 144-148) is a separate guard
file with the same assertions:

> If keeping validator-implementation guards separate reads cleaner,
> add `infra/tests/test_validate_access_policy_local_probes.py`
> instead of extending `test_public_intake_policy_fixture.py`. The
> required assertions are the same: the validator must contain both
> public probe payloads and expected decision checks.

Either way, the guard reads the validator's script source, not a
"validator must run probes" comment in CI documentation. A regression
that deletes the public probes from the validator (intentionally or by
merge accident) fails the guard test in CI, so the runtime check
cannot be removed while the static fixture tests still pass.

TG-2 (proposal lines 184-199) names the guard test execution:

> Run the public-intake fixture tests:
>
> ```bash
> pytest infra/tests/test_public_intake_policy_fixture.py
> ```
> ...
> - the validator script contains the public submit and public read
>   live probe payloads and expected decision checks.

**Risk:** the natural shortcut would be (a) skip the guard entirely,
so the runtime probes can later be deleted from the validator script
without any test failing (the static fixture tests would all still
pass since the policy text is unchanged), (b) write a guard that only
checks the matrix YAML still names the public cases, since matrix
coverage is what already exists and adding a pytest assertion on
`access_policy_matrix.yml` does not prove the validator actually runs
those cases at runtime, or (c) write a guard that asserts a property
on a wrapper Python module rather than reading the shell script — a
refactor that moves the curl logic elsewhere would let the validator
silently lose the probes.

**Mitigation:** the guard reads the actual validator shell script
file's text and asserts four exact substrings appear. The existing
"omits" assertion is flipped to "contains," forcing the replacement
during this slice and proving the probes are present in the script
the runtime lane actually executes.

**Verdict:** Not a shortcut.

## C4 — No "TODO: matrix-driven later" stubs

**Pass.**

Q2 (proposal lines 56-77) explicitly addresses the matrix-runner
question and **does not leave a TODO**:

> The stronger long-term pattern is a matrix runner derived from
> `infra/tests/fixtures/contracts/access_policy_matrix.yml`, but that is
> larger than this BL-012 slice because the existing validator has
> hand-written runtime payloads and shell-side assertions for only the
> sample `User::` allow/deny case. Converting the script into a general
> YAML matrix runner would broaden the diff, change failure output for
> existing probes, and invite unrelated coverage decisions about
> service identities.
>
> For this proposal, the contract matrix remains the source of static
> intended decisions, and the validator gets the minimum live coverage
> that closes the `Public::` runtime gap.

§5 (Anti-scope, proposal lines 220-221) closes the door on a stub:

> Do not convert the validator into a full matrix runner in this slice.
> That is larger than needed to close BL-012 and should be proposed
> separately if wanted.

This matters: the alternative — drop a `# TODO: replace with matrix
runner` comment beside the new payload variables and call the slice
done — would leave the validator carrying a known half-implementation
that the next reviewer would either expand into scope creep or quietly
delete. The proposal instead lands two real, hardcoded payloads
beside the existing real, hardcoded `allow_payload` and `deny_payload`
(script line 191-192 today), which is the same pattern the validator
already uses for `User::`. The new payloads are not stubs; they are
working probes. The matrix runner is anti-scoped, not deferred-as-TODO.

The diff budget (proposal lines 224-238) reinforces this: "two
payload variables, four curl invocations inside the proof command,
four log lines, and focused shell assertions for public submit/public
read decisions" — concrete code, not placeholder hooks. There is no
"matrix runner skeleton" being added with the public payloads as the
only entry, nor any "if MATRIX_MODE then ..." branching that ships
half a feature.

The pytest guard side (§3 lines 136-148, alt lines 144-148) is also
free of stub-shape: the guard either replaces the existing "omits"
assertion in `test_public_intake_policy_fixture.py` (one small flip)
or adds a parallel small guard file with the same assertions. Neither
shape introduces a TODO surface. The matrix-runner generalization is
clearly tagged as a separate proposal if wanted later (proposal
lines 215-221), so it has its own intake path rather than rotting
inside BL-012.

**Risk:** the natural shortcut would be (a) ship a placeholder
"matrix runner harness" that loops over a one-row list (just the
public Allow/Deny pair) with a "TODO: extend rows from
access_policy_matrix.yml" comment, so the new code looks general but
covers only what the two hardcoded payloads would have covered, or
(b) leave a `# TODO: parameterize from matrix` line beside the
hardcoded payloads, inviting a follow-up that may or may not happen.

**Mitigation:** the proposal locks two hardcoded payloads beside the
existing two hardcoded payloads (mirroring the existing shape, not
introducing a new generalization), and the matrix runner is named in
anti-scope as a separate future proposal — not a deferred-stub
inside this slice.

**Verdict:** Not a shortcut.

## Verdict reasoning

BL-012 ships exactly the contour the gate watches for:

- Two real HTTP `POST` probes to
  `http://opal-client:8180/v1/is_authorized` against the in-cluster
  OPAL client, gated on `/v1/policies` hydration of the canonical
  policy IDs, on the same runtime lane as the existing access policy
  validator. Static fixture tests stay (policy-text drift coverage),
  and `--static-only` is explicitly not allowed to claim coverage of
  this class of OPAL/Cedar behavior change.

- Both directions are exercised: Allow on
  `application:submit_public` and Deny on `api:read`, both for the
  same `Public::"web-intake.local"` principal, run before and after
  the existing 30-second polling-interval sleep, with cardinality
  assertions ("exactly one allow line, exactly one deny line") and
  named failure wording for decision-time and hydration-time
  rejection.

- The pytest guard reads the validator's shell script source and
  asserts the four payload substrings appear. The existing
  `test_public_intake_policy_fixture.py:101-113` assertion is flipped
  from "omits" to "contains," so the slice cannot land without
  updating the guard, and the guard cannot be silently dropped
  without breaking CI. An alternate split-out file is acceptable
  with the same assertions.

- The matrix-runner generalization is anti-scoped, not deferred as a
  TODO inside the validator. The new payloads are real,
  ship-as-working entries beside the existing `User::` payloads,
  matching the validator's current hardcoded-payloads shape rather
  than introducing a half-built generalization layer.

The slice is appropriately small (proposal §6 caps script churn at
~60 lines and pytest churn at ~35 lines, no production code, no
policy bundle changes, no GitOps manifest changes), runs on the lane
that actually catches the failure mode (live OPAL/Cedar decision
boundary), and has no TODO-shape stubs.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/bl-012-shortcut.md
