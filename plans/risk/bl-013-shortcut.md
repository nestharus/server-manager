# BL-013 — Shortcut risk gate (public-intake channel tripwire)

**Verdict:** LOW

Scope: BL-013 proposes a static CI tripwire (one new pytest file,
`infra/tests/test_public_intake_channel_tripwire.py`) that enumerates
non-local directories under `gitops/channels/`, detects when any of them
ship public-intake-relevant `applications/server-manager/` material, and
asserts the full four-item public-intake substrate group exists for that
channel. The shortcut gate inspects whether the slice (1) walks
`gitops/channels/*` rather than hard-coding `local`, (2) actually
materializes synthetic-channel fixtures for negative and positive cases
rather than skipping them or marking them TODO, (3) genuinely checks all
four substrate items rather than 1-of-4 plus a generic "shape" assertion,
and (4) avoids "TODO: validate Pomerium routes more strictly later"
stubs.

Source: `proposals/32-bl-013-channel-tripwire.md`,
`research/47-bl-013-tripwire-problem-map.md`,
`infra/channels/dev.yaml`,
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`,
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`,
`policy/cedar/channels/local/services/server-manager-api/policies.json`.

## C1 — Real glob walk over `gitops/channels/*` (not hardcoded `local`-only)

**Pass.**

The proposal locks the trigger detection at Q1 (proposal lines 38-59) on
"every non-local directory under `gitops/channels/`" and explicitly skips
`local` as the reference channel covered by existing tests. The substrate
section (proposal lines 134-141) calls this out as an enumeration, not a
hard-coded list:

> - Enumerate directories under `gitops/channels/`, excluding `local`.
> - Parse YAML using the repository's existing `yaml.safe_load_all`
>   style.
> - Detect public-intake relevance from the trigger rules in Q1.
> - For triggered channels, assert the group items from Q2.

This is a real walk, not a `for channel in ["local"]:` loop. The current
repository state has only `gitops/channels/local/` (verified: `ls
gitops/channels/` returns `local` alone), so the live walk produces an
empty set today, but the test will pick up `gitops/channels/dev/` or any
other future channel directory the moment it is materialized — which is
the entire point of a tripwire. The research document independently
confirms this enumeration shape at lines 184-194 of
`research/47-bl-013-tripwire-problem-map.md`:

> - Add one Python infra test that enumerates non-local directories
>   under `gitops/channels/`.
> - Skip absent channels naturally by walking only existing directories.

The trigger-detection signals listed in Q1 are an OR-set across four
distinct surfaces (public Ingress paths, the `public-intake-rate-limit`
filename, named resources, and Kustomization references), so a future
remote channel cannot quietly slip through by, e.g., renaming the file
while keeping the public ingress paths.

The proposal also correctly disambiguates between channel-presence and
channel-relevance: TG-1 acceptance (proposal lines 162-169) explicitly
states `policy/cedar/channels/dev/` does not trigger by itself and an
absent `gitops/channels/dev/` does not fail. This forecloses both
shortcut directions — neither "any directory presence triggers"
(over-broad) nor "only the local channel exists, so why bother walking"
(under-broad).

**Risk:** the natural shortcut would be (a) iterate
`["local"]` and never look elsewhere because `gitops/channels/` only
contains `local` today, leaving the tripwire dead until someone manually
adds a new channel to a constant; or (b) walk `gitops/channels/*` but
include `local`, which would either duplicate the existing local-channel
assertions or — more dangerously — rewrite them in a less strict shape
and let the local tests drift.

**Mitigation:** the proposal locks "exclude `local`" as the only
allow-list entry and walks the rest of `gitops/channels/*` dynamically,
which keeps the existing local tests authoritative for local while the
new test owns cross-channel completeness.

**Verdict:** Not a shortcut; the walk is a real glob and `local` is the
only deliberate exclusion, with stated reasoning.

## C2 — Real fixture for synthetic-channel test (not skipped/marked TODO)

**Pass.**

The proposal calls for two fixture-based tests, both materializing
concrete substrate trees under `tmp_path`:

- TG-2 (proposal lines 171-182): synthesize a fake non-local channel
  with public-intake-relevant `applications/server-manager` material
  AND only part of the substrate group; assert the tripwire detects
  the fake channel as relevant, the assertion fails, and the failure
  text names the channel and every missing item.
- TG-3 (proposal lines 184-199): synthesize a fake non-local channel
  with the full substrate group (API-side
  `public-intake-rate-limit.yaml`, Pomerium-side
  `public-intake-rate-limit.yaml`, Cedar policies using
  `Public::"web-intake.<fake-channel>"`, Pomerium config routes
  covering the public web paths); assert the tripwire detects it as
  relevant and all required group checks pass.

The substrate section explicitly requires fixture helpers, not skip
markers (proposal lines 140-141):

> - Provide fixture helpers that can run the same tripwire logic
>   against a temporary synthetic channel root for negative and
>   positive tests.

This is the exact opposite of the failure mode the gate watches for. A
shortcut-shaped slice would have written something like
`@pytest.mark.skip("requires future dev channel materialization")` on
the tripwire test and shipped only the repository-state check (TG-1),
which would pass vacuously today since no non-local channel exists. The
proposal forecloses that path by requiring both the negative
(partial-fixture-fails) and positive (full-fixture-passes) cases to be
implemented as real fixtures with channel-derived values.

The TG-3 acceptance line "the fixture proves the test is channel-derived
and does not rely on `web-intake.local` or local hostnames" (proposal
line 199) is a deliberate guard against a different fixture-shaped
shortcut: copying the local substrate verbatim into the fake channel
and only renaming the directory. That would silently pass the structural
checks while leaving the `local` principal/host wiring intact — a real
hazard given how tempting "copy local, rename, ship" is. The
channel-derived requirement (Q3 locks `Public::"web-intake.<channel>"`,
Q2 §4 calls out non-local hostname pattern `api.<channel>.humility.gg` /
`web.<channel>.humility.gg`) makes that shortcut visible to the test.

The diff budget (proposal §6, ~180-260 lines) is sized to absorb both
fixtures and their helpers. There is no "fixture in a follow-up slice"
deferral.

**Risk:** the natural shortcut would be (a) ship only TG-1 (the
repository-state check) and skip TG-2/TG-3 with `pytest.mark.skip`,
leaving the tripwire untested against any concrete failure case; or (b)
implement TG-2/TG-3 but reuse the local substrate verbatim under a
renamed directory, so the synthetic channel tests pass against
`web-intake.local` and `api.local.humility.local` — drift the tripwire
is supposed to catch.

**Mitigation:** the proposal explicitly requires fixture helpers and
channel-derived expected values; TG-3's "does not rely on
`web-intake.local` or local hostnames" line is the explicit guard
against the verbatim-copy shortcut. The diff budget accommodates both
fixtures.

**Verdict:** Not a shortcut; both negative and positive synthetic
channel fixtures are mandated, with channel-derived values.

## C3 — All 4 substrate items genuinely checked (not 1-of-4 + generic assertion)

**Pass.**

Q2 (proposal lines 62-104) locks four substrate items, each with
concrete kind/name/path/annotation requirements rather than a
shape-only check:

1. **API-side KongPlugin and public-only Ingress.**
   `gitops/channels/<channel>/applications/server-manager/public-intake-rate-limit.yaml`
   must contain `KongPlugin/public-intake-rate-limit` and
   `Ingress/server-manager-public-intake-api`. The Ingress must use
   `konghq.com/plugins: public-intake-rate-limit` and expose
   `/api/v1/public/applications` and `/api/v1/public/chapters` as
   path-specific `Prefix` routes to `server-manager-api:8000`. Concrete:
   names the kind, the resource name, the annotation, the literal
   paths, the pathType, and the upstream service:port.

2. **Web-side Pomerium/Kong public-only Ingress.**
   `gitops/channels/<channel>/auth/pomerium/public-intake-rate-limit.yaml`
   must contain `Ingress/web-public-intake` with the same plugin
   annotation and expose `/api/public/applications`,
   `/api/public/chapters`, and legacy `/api/applications` as
   path-specific `Prefix` routes to `pomerium-proxy:80`. Concrete in
   the same shape as item 1.

3. **Cedar public principal policy.**
   `policy/cedar/channels/<channel>/services/server-manager-api/policies.json`
   must include both:
   - `public-intake-allow` permitting
     `Public::"web-intake.<channel>"` to perform
     `Action::"application:submit_public"` on
     `Resource::"server-manager-api:public-applications"`;
   - `public-intake-no-read` forbidding the same principal from
     `Action::"api:read"` on `Resource::"server-manager-api"`.
   Concrete: names the file, both policy IDs, the channel-derived
   principal, and the action/resource pairs for permit and forbid.
   This is two assertions (allow + forbid), not one.

4. **Pomerium route coverage.**
   `gitops/channels/<channel>/auth/pomerium/secrets-infisicalsecret.yaml`
   must exist; its `pomerium-config` rendered `config.yaml` must
   include web-host routing that lets public application requests
   reach `server-manager-web.web.svc.cluster.local:8080` with
   `allow_public_unauthenticated_access: true`; identity-bearing
   web/API routes for the same web host must remain explicit and
   ordered before the public catch-all so protected paths are not
   shadowed. Concrete: names the file, the config key, the upstream
   FQDN:port, the auth flag, and the ordering invariant.

The hostname-pattern lock at proposal lines 99-103 is grounded in repo
config: `infra/channels/dev.yaml:83` sets `remote_domain: humility.gg`,
so the rejection of `api.local.humility.local` /
`web.local.humility.local` in non-local substrate and the expected
`api.<channel>.humility.gg` / `web.<channel>.humility.gg` pattern is
not a guess — it is the channel config's declared remote domain.

Q4 (proposal lines 119-130) requires aggregate failure messages naming
the channel and every missing or invalid item. That is an aggregate
*report*, not an aggregate check — the test still has to evaluate each
of the four items independently to know which are missing or invalid.
A 1-of-4 check that bailed on the first failure would not satisfy "name
… every missing item, using the format locked in Q4" (TG-2 acceptance,
proposal line 181).

The supported-surface anti-list shape from BL-014 (assert public-intake
plugin is *not* on adjacent catch-all ingresses) is not asked for in
BL-013 because BL-013's tripwire scope is completeness of the public-
intake group, not non-bleed; the BL-014 / `test_public_intake_rate_limit.py`
guard already covers non-bleed for the local channel and the same
binding-pattern requirement (per-Ingress
`konghq.com/plugins: public-intake-rate-limit`) is required by item
1/2 above on remote channels too. The two slices are complementary,
not overlapping.

**Risk:** the natural shortcut would be (a) check only item 1
(`public-intake-rate-limit.yaml` exists in the API directory) and treat
the others as "follows from item 1 by convention," skipping concrete
parses of the Pomerium ingress, Cedar JSON, and Pomerium config; or (b)
reduce item 3 to "Cedar policies file exists" without parsing the
JSON for both the allow and forbid statements, which is exactly the
"shape, not content" failure mode the gate watches for; or (c)
drop item 4 (Pomerium config routes) entirely on the grounds that
parsing the rendered `pomerium-config` is fiddly, replacing it with
"the secret file exists."

**Mitigation:** Q2 enumerates concrete fields under each of the four
items with names, paths, annotations, and required values; Q4 requires
aggregate failure messages that necessarily evaluate each item
independently; TG-2 requires the failure to name "every missing item,"
which forces independent checks. The Cedar item is split into two
separate policy assertions (allow + forbid) so item 3 alone is two
checks. The Pomerium config item names a specific upstream FQDN, port,
and auth flag rather than asking only for "some route to be present."

**Verdict:** Not a shortcut; all four items are enumerated with
concrete shape requirements and the failure-message format forces
independent evaluation of each.

## C4 — No "TODO: validate Pomerium routes more strictly later" stubs

**Pass.**

The Pomerium route coverage requirement (item 4, proposal lines 90-97)
is concrete, not a stub:

- The file path is named:
  `gitops/channels/<channel>/auth/pomerium/secrets-infisicalsecret.yaml`.
- The config surface is named: rendered `config.yaml` inside
  `pomerium-config`.
- The upstream is named: `server-manager-web.web.svc.cluster.local:8080`.
- The auth flag is named: `allow_public_unauthenticated_access: true`.
- The ordering invariant is named: identity-bearing web/API routes for
  the same web host remain explicit and ordered before the public
  catch-all so protected paths are not shadowed.

This is the same shape `test_public_intake_rate_limit.py` already
exercises against the local channel (the research file confirms at
lines 62-68 of `research/47-bl-013-tripwire-problem-map.md`), not a
stub or TODO marker.

The anti-scope section (proposal §5, lines 201-216) is clean. It
explicitly forbids:

- runtime apply, Flux reconciliation, DNS, certificate issuance,
  external ingress, browser e2e, or live Pomerium/Kong smoke checks
  (these are real anti-scope items with stated reasoning, not
  deferred work);
- modifying any existing channel's manifests;
- implementing the `dev` channel materialization or BL-013's full
  remote-channel scope (the missing remote GitOps channel remains the
  blocker; this slice only makes future partial materialization fail
  fast);
- compatibility shims, alternate principal names, feature flags,
  deprecated aliases, or dual support for local and channel-derived
  public principals.

Each of these is a deliberate anti-scope decision with stated
reasoning, matching the pattern BL-014 used correctly for live KIC
smoke. There is no implicit "extend later" surface — the proposal
distinguishes clearly between (a) what this slice covers (static
cross-channel completeness check), (b) what is anti-scoped with reasons
(runtime checks, channel materialization itself, compatibility shims),
and (c) what stays in existing tests (local-channel semantic coverage).

The TG-3 line "the fixture proves the test is channel-derived and does
not rely on `web-intake.local` or local hostnames" (proposal line 199)
is also a guard against the implicit-stub shape: a shortcut
implementation could ship the four items but copy the local hostnames
into the fake channel fixture and call it done, which would leave the
hostname-derivation logic effectively untested. The proposal closes
that.

The Q1 trigger conditions are also concrete and not deferred. A
shortcut-shaped trigger would say "trigger when the channel exists" or
"trigger when any YAML in `applications/server-manager/` mentions
public" with a TODO to refine later. Q1 instead enumerates four
specific signals (public Ingress paths, the literal filename, named
resources, Kustomization references) and locks them.

The two soft observations below are not shortcuts — they are notes for
implementation review, not gate failures:

1. TG-2 calls for "only part of the substrate group" but does not
   parametrize across the four possible missing-item scenarios. A
   single fixture with multiple items missing exercises the aggregate
   failure-message path but does not independently prove each of the
   four items is checked. The implementation should consider a
   parametrized fixture covering each missing-item case (or, at
   minimum, a fixture that omits each of the four substrate files in
   turn). The diff budget (180-260 lines) accommodates this; the
   proposal text does not require it but does not foreclose it either.

2. TG-1's repository-state acceptance ("absent `gitops/channels/dev/`
   does not fail" and "existing `policy/cedar/channels/dev/` does not
   trigger the tripwire by itself") is currently verified only
   indirectly through the live walk plus the fact that the current
   repo state happens to match those conditions. A more durable proof
   would be a fixture that materializes a `policy/cedar/channels/<fake>/`
   directory with no `gitops/channels/<fake>/` and asserts the
   tripwire produces no failure. Again, the proposal does not require
   this, but the implementation could add it.

Neither observation is shortcut-shaped — both are "consider doing more"
notes, not "the proposal silently skipped this surface" findings. The
proposal text is internally complete; these would be incremental
strengthenings if the implementation has room.

**Risk:** the natural shortcut would be (a) leave the Pomerium route
coverage check at "secret file exists" with a `# TODO: validate routes
more strictly` comment in the test code; or (b) ship TG-2 with a
single missing-item fixture and never come back to verify each item
individually, leaving 1-of-4 effective coverage; or (c) lift the
hostname-pattern check into a "validate later" stub on the grounds that
"we don't have a remote channel yet to test against."

**Mitigation:** item 4 is locked with concrete upstream/port/auth-flag/
ordering requirements; the anti-scope section names every deferred
surface with stated reasoning rather than leaving them as implicit
extend-later stubs; TG-3 explicitly guards against the verbatim-copy
shortcut by requiring channel-derived values. The two soft
observations are implementation-strength notes, not proposal-shape
gaps.

**Verdict:** Not a shortcut; no "validate later" stubs in scope, all
deferred surfaces are explicitly anti-scoped with reasoning.

## Verdict reasoning

BL-013 fits the contour the gate watches for cleanly:

- The trigger walks `gitops/channels/*` dynamically with `local` as the
  only deliberate exclusion, not a hard-coded `["local"]` loop.
  Absence of remote channels and policy-only directories are explicitly
  acknowledged as non-trigger states, with stated reasoning. The four
  trigger signals (public Ingress paths, filename match, resource
  names, Kustomization references) form an OR-set across distinct
  public-intake surfaces.

- Both negative (partial substrate fails) and positive (full substrate
  passes) synthetic-channel fixtures are mandated under `tmp_path`
  with channel-derived values. The TG-3 line forbidding reliance on
  `web-intake.local` or local hostnames forecloses the verbatim-copy
  shortcut. The diff budget (180-260 lines) accommodates both fixtures
  plus helpers.

- All four substrate items are enumerated with concrete shape
  requirements (kind, resource name, path, annotation, upstream,
  pathType, auth flag, ordering invariant). The Cedar item is split
  into two policy assertions (allow + forbid). The hostname pattern
  is grounded in `infra/channels/dev.yaml`'s `remote_domain:
  humility.gg`, not invented. Q4's aggregate failure-message format
  forces independent evaluation of each item, since the failure has to
  name every missing item.

- Anti-scope is clean: live runtime checks, channel materialization,
  compatibility shims, alternate principal names, and feature flags are
  all explicitly excluded with stated reasoning. There are no implicit
  "validate later" surfaces. The Pomerium route coverage check is
  concrete, not a stub.

The two soft observations — TG-2 not parametrized across each missing-
item scenario, and TG-1's negative-trigger case verified only
indirectly through current repo state — are implementation-strength
notes the slice could address within budget but are not shortcut-shaped
omissions in the proposal. The proposal text is internally complete;
these would be incremental strengthenings of the test surface, not
closures of a gap the proposal silently left open.

The slice is appropriately small (one new test file, no production
code, no GitOps manifest changes, no policy bundle changes), runs on
the right lane (static CI tripwire that fires the moment a future
non-local channel ships public-intake material), correctly defers
runtime/Flux/DNS/cert/e2e to anti-scope with reasoning, and
correctly leaves existing local-channel tests as the local semantic
coverage rather than rewriting or duplicating them. There is no
concrete shortcut to flag.

Verdict: LOW. All four checks pass; the two soft observations are
implementation polish, not gate failures.

SHORTCUT_DONE: plans/risk/bl-013-shortcut.md
