# INIT-138 — Shortcut risk gate (remote channel public-intake substrate)

**Verdict:** LOW

Scope: INIT-138 — narrow Option A port that materializes the
`gitops/channels/dev/` public-intake substrate required by
BL-013's tripwire. The slice adds three GitOps manifests
(`applications/server-manager/public-intake-rate-limit.yaml`,
`auth/pomerium/public-intake-rate-limit.yaml`,
`auth/pomerium/secrets-infisicalsecret.yaml`) plus a top-level
`gitops/channels/dev/kustomization.yaml`, and appends two Cedar
policies (`public-intake-allow`, `public-intake-no-read`) to
`policy/cedar/channels/dev/services/server-manager-api/policies.json`.

The shortcut gate inspects whether INIT-138 ships real
channel-derived hostnames (not "TODO: change later"
placeholders), full materialization of all four substrate items
(not `# add later` stubs), both halves of the Cedar policy pair
(allow + forbid), real kustomize wiring (no "skip wiring for
now"), and tests that genuinely exercise the new dev manifests
rather than asserting only on the existing local channel.

Source: `proposals/33-init-138-remote-channel-public-intake.md`,
`research/48-init-138-remote-channel-problem-map.md`,
`infra/tests/test_public_intake_channel_tripwire.py` (existing
BL-013 tripwire).

## C1 — Real channel-derived hostnames (not "TODO: change later")

**Pass.**

Q2 (proposal lines 52-75) locks the full channel-derived value
table for `dev` with explicit final values, not placeholder
stubs:

> ```text
> API hostname:      api.dev.humility.gg
> Web hostname:      web.dev.humility.gg
> Protected API:     protected-api.dev.humility.gg
> Authenticate URL:  https://authenticate.dev.humility.gg
> IdP provider URL:  https://auth.dev.humility.gg/application/o/pomerium/
> Public principal:  Public::"web-intake.dev"
> ```

The derivation is grounded: the hostname domain comes from
`infra/channels/dev.yaml`'s `ingress.remote_domain: humility.gg`,
and the auth host convention is already used by the dev
access-policy issuer
(`https://auth.dev.humility.gg/application/o/humility-service-identities/`).
These are not "TODO: change later" — they are the values the
manifests must contain at slice landing.

The proposal also explicitly bans the local equivalents from
appearing in dev manifests (Q2 lines 70-75):

> Do not use `*.local.humility.local`, `web-intake.local`,
> `Service::"*.local"`, `/auth/local/...`, local Step CA issuers,
> local ingress TLS secret names, or local DNS aliases in the
> new dev public-intake manifests.

with the one allowed carve-out for the Kubernetes internal
service DNS suffix `.svc.cluster.local`, which is not a Humility
channel id. TG-5 (lines 284-298) backs this with a regex sweep
over `gitops/channels/dev/` and the dev Cedar policy file that
rejects `*.local.humility.local`, `web-intake.local`,
`/auth/local/`, `/postgres/local/`, `/object-storage/local/`,
`/runtime/local`, local Step CA issuer annotations, local
ingress TLS secret names, and `policy/cedar/channels/local`
references — but explicitly does not reject `.svc.cluster.local`.

**Risk:** the shortcut would be (a) seed dev manifests with a
copy of the local channel's `*.local.humility.local` hosts and a
"// TODO: rename to dev.humility.gg before merge" comment, (b)
parameterize on a generic `${CHANNEL_DOMAIN}` token without ever
materializing the value, or (c) use `web-intake.local` as the
public principal because "the BL-013 tripwire only checks for
the policy id, not the principal value."

**Mitigation:** Q2 enumerates the final hostnames explicitly,
the BL-013 tripwire validates `Public::"web-intake.<channel>"`
against the channel id (research lines 209-210, "Cedar policies
use `Public::\"web-intake.dev\"`"), TG-5 sweeps regex for local
host strings in dev files, and TG-3 (proposal line 263) names
"neither policy contains `Public::\"web-intake.local\"`" as an
explicit negative case.

**Verdict:** Not a shortcut.

## C2 — All 4 substrate items real (not `# add later` stubs)

**Pass.**

§3 (Substrate → New files, proposal lines 158-197) gives a
field-level contract for each of the four substrate items. None
are `# add later` stubs.

**(1) `gitops/channels/dev/kustomization.yaml`** — Q5 (lines
137-153) names the resources list inline:

> ```yaml
> resources:
>   - applications/server-manager/public-intake-rate-limit.yaml
>   - auth/pomerium/public-intake-rate-limit.yaml
>   - auth/pomerium/secrets-infisicalsecret.yaml
> ```

with the explicit anti-scope that intermediate
`applications/`, `applications/server-manager/`, `auth/`, and
`auth/pomerium/` kustomizations are not added in this slice.
Direct file references, no placeholder kustomization.

**(2) `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`**
— §3 (lines 162-172) lists `KongPlugin/public-intake-rate-limit`
in namespace `server-manager`, `Ingress/server-manager-public-intake-api`
in namespace `server-manager`, host `api.dev.humility.gg`,
prefix paths `/api/v1/public/applications` and
`/api/v1/public/chapters`, backend `server-manager-api:8000`,
no local Step CA annotations, no local TLS secret names. The
`config.policy: local` field from local's KongPlugin is
explicitly handled — "omit the policy field for this static
slice" — not silently carried.

**(3) `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`**
— §3 (lines 174-180) lists `Ingress/web-public-intake` in
namespace `auth-system`, host `web.dev.humility.gg`, prefix
paths `/api/public/applications`, `/api/public/chapters`,
`/api/applications`, backend `pomerium-proxy:80`, no local Step
CA annotations or local TLS secret names.

**(4) `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`**
— §3 (lines 182-196) lists the Pomerium config-bearing manifest
with `config.yaml` under `managedSecretReference.template.data`
(so the BL-013 parser can validate the route block), dev route
sources (`https://web.dev.humility.gg`,
`https://protected-api.dev.humility.gg`), dev Pomerium URLs
(`authenticate_service_url: https://authenticate.dev.humility.gg`,
`idp_provider_url: https://auth.dev.humility.gg/application/o/pomerium/`),
no local-only `insecure_server` or `grpc_insecure` settings, and
the explicit boundary that runtime secret sourcing for dev
Infisical remains anti-scope until a dev `auth_stack`/Infisical
contract exists.

The Pomerium route ordering is also fully specified, not deferred.
Q4 (lines 109-119) names the minimum identity-bearing routes
that must come before the public catch-all (`/api/me`,
`/api/web/admin/`, `/api/web/officer/`, `/applications/queue`
and `/applications/queue/`, `/applications/`, `/admin`,
`/auth/discord/`) and the public catch-all to
`http://server-manager-web.web.svc.cluster.local:8080`. Public
ingress paths and API ingress paths are enumerated identically
in Q4 (lines 121-136).

**Risk:** the shortcut would be (a) ship `kustomization.yaml`
with the resources list but the three manifest files containing
only `apiVersion: v1\nkind: ConfigMap\n# TODO: real public-intake
ingress` placeholders, (b) ship the API and web public ingresses
but defer the Pomerium route block ("we'll wire routes in a
follow-up") so the BL-013 tripwire's route validation has nothing
to bind against, or (c) drop the Pomerium config-bearing manifest
and rely on a "static equivalent" placeholder.

**Mitigation:** §3 names the kinds, namespaces, hosts, paths,
and backends for each manifest; Q4 enumerates Pomerium route
ordering; the BL-013 tripwire (`infra/tests/test_public_intake_channel_tripwire.py`)
validates the route block exists with identity-bearing routes
before the public catch-all (research lines 213-217); TG-2
(proposal lines 237-249) parses the embedded
`managedSecretReference.template.data.config.yaml` and asserts
the public catch-all and absence of local route sources; TG-4
(lines 270-282) runs `kustomize build gitops/channels/dev/` and
asserts the API `KongPlugin`, `Ingress/web-public-intake`, and
the Pomerium config-bearing manifest are present in the output.

**Verdict:** Not a shortcut.

## C3 — Cedar policy Allow + Deny BOTH present (no half-policy)

**Pass.**

Q3 (proposal lines 77-100) requires both halves of the public-
intake policy pair, with full Cedar bodies inline:

> ```cedar
> permit(
>   principal == Public::"web-intake.dev",
>   action == Action::"application:submit_public",
>   resource == Resource::"server-manager-api:public-applications"
> );
>
> forbid(
>   principal == Public::"web-intake.dev",
>   action == Action::"api:read",
>   resource == Resource::"server-manager-api"
> );
> ```

The policy IDs are also fixed: `public-intake-allow` and
`public-intake-no-read` (Q3 lines 97-99), keyed on the canonical
ids that the BL-013 tripwire matches against. There is no path
where only the `permit` half ships and the `forbid` is left as
"to be added in a follow-up."

§3 (Modified files, lines 200-204) reaffirms the same: append
**both** policies to
`policy/cedar/channels/dev/services/server-manager-api/policies.json`,
preserving the existing dev user / Buildkite / Crossplane
policies. Not "append public-intake-allow now, forbid later."

TG-3 (lines 252-267) covers both policies as required test
inputs:

> - policy contents include syntactically complete Cedar
>   statements for `public-intake-allow` and `public-intake-no-read`;
> - both policies use `Public::"web-intake.dev"`;
> - neither policy contains `Public::"web-intake.local"`.

The "syntactically complete Cedar statements for **both**" line
is the one that closes the half-policy door at test time: a
slice that ships only the allow rule fails the assertion that
`public-intake-no-read` is present.

The proposal also explicitly forbids adding a service-identity
entry for the public principal (Q3 lines 99-100): "Do not add a
service identity entry for public intake; the principal is a
public/anonymous Cedar principal, not an authenticated service
account." This rules out the related shortcut of treating the
public principal as a service identity that could bypass the
forbid.

**Risk:** the shortcut would be (a) ship only `public-intake-allow`
and rely on Cedar's default-deny to "implicitly forbid reads"
without the explicit `public-intake-no-read` forbid policy, (b)
ship both policies but with the same principal name as local
(`Public::"web-intake.local"`) so the BL-013 tripwire's
channel-derived assertion fails silently against the existing
allow policy, or (c) ship the forbid as a comment / TODO line
in the JSON file.

**Mitigation:** Q3 lists both Cedar bodies inline with the dev
public principal; the BL-013 tripwire keys on canonical policy
ids (research lines 217-218), so a missing `public-intake-no-read`
fails the substrate verification; TG-3 explicitly asserts
"syntactically complete Cedar statements for `public-intake-allow`
**and** `public-intake-no-read`"; TG-3 line 263 asserts neither
policy uses the local principal.

**Verdict:** Not a shortcut.

## C4 — No "skip kustomize wiring for now" stubs

**Pass.**

Q5 (proposal lines 137-153) requires the top-level
`gitops/channels/dev/kustomization.yaml` to ship in this slice,
not a follow-up:

> Add a top-level `gitops/channels/dev/kustomization.yaml`.
>
> It should reference only the three dev public-intake manifest
> files directly:
>
> ```yaml
> resources:
>   - applications/server-manager/public-intake-rate-limit.yaml
>   - auth/pomerium/public-intake-rate-limit.yaml
>   - auth/pomerium/secrets-infisicalsecret.yaml
> ```

The narrowing is deliberate, not a shortcut: intermediate
`applications/`, `applications/server-manager/`, `auth/`, and
`auth/pomerium/` kustomizations are explicitly out of scope for
this slice. That is structural narrowness ("don't imply that the
rest of the dev channel exists"), not "skip kustomize wiring for
now." The top-level `kustomization.yaml` is real, references
three real manifests, and is verified at test time.

TG-4 (proposal lines 270-282) runs the actual kustomize build:

> ```bash
> kustomize build gitops/channels/dev/
> ```
>
> Acceptance:
>
> - build exits successfully;
> - output includes the API-side `KongPlugin` and `Ingress`;
> - output includes `Ingress/web-public-intake`;
> - output includes the Pomerium config-bearing manifest.

The acceptance criteria are output-content checks, not just
"`kustomize build` exits 0" — so a `kustomization.yaml` with
empty `resources: []` would pass exit code but fail the
content-presence assertions. The "skip wiring for now" stub
therefore fails the test plan.

§6 (Diff budget, proposal lines 322-330) explicitly lists
`gitops/channels/dev/kustomization.yaml` as part of the expected
GitOps diff alongside the three manifest files, confirming it
is a slice deliverable, not a follow-up.

**Risk:** the shortcut would be (a) ship the three manifests
without a `kustomization.yaml` and rely on Flux's "if no
kustomization, treat as raw manifests" fallback (which doesn't
exist for `kustomize build`), (b) ship a `kustomization.yaml`
with `resources: []` and a comment "// TODO: wire after BL-013
lands," or (c) ship a `kustomization.yaml` that references only
one of the three manifests and defer the rest.

**Mitigation:** Q5 lists all three resources inline; TG-4
asserts each manifest's output is present in the kustomize
build, not just a clean exit; the diff budget §6 lists the
kustomization as an explicit deliverable.

**Verdict:** Not a shortcut.

## C5 — Tests genuinely exercise the dev manifests (not "trust local" placeholder assertions)

**Pass with one documented degradation path (Cedar parser
availability).**

The test plan binds against the real dev manifests at five
layers, not against the existing local channel:

**TG-1 (proposal lines 218-234) — BL-013 tripwire discovers and
validates dev.** Runs `pytest infra/tests/test_public_intake_channel_tripwire.py`.
Acceptance includes `discover_channels()` returns `dev` after the
new API-side manifest exists and `verify_substrate("dev")`
returns no failures, plus four channel-derived assertions:

> - the API ingress uses `api.dev.humility.gg`;
> - the Pomerium/web ingress uses `web.dev.humility.gg`;
> - Cedar policies use `Public::"web-intake.dev"`;
> - Pomerium route ordering keeps identity-bearing web routes
>   before the public catch-all.

This is the existing BL-013 tripwire (research lines 211-218,
proposal lines 207-214) discovering the new dev substrate,
not a freshly written assertion that "trust local also covers
dev." The proposal explicitly preserves the tripwire as-is:
"No change should be required to
`infra/tests/test_public_intake_channel_tripwire.py`. It already
discovers non-local channels through
`gitops/channels/<channel>/applications/server-manager` and
validates channel-derived hosts and `Public::\"web-intake.<channel>\"`."

**TG-2 (lines 236-249) — dev Pomerium route block parses.**
Parses the new Pomerium manifest with `yaml.safe_load_all`, then
parses the embedded `managedSecretReference.template.data.config.yaml`
with `yaml.safe_load`. Acceptance includes:

> - the embedded Pomerium config is valid YAML;
> - the embedded config has a `routes` list;
> - the web public catch-all route points to
>   `http://server-manager-web.web.svc.cluster.local:8080`;
> - no route source contains `web.local.humility.local` or
>   `protected-api.local.humility.local`.

This binds against the actual dev Pomerium manifest's embedded
config — a "trust local" placeholder ("the local channel covers
this, dev inherits") would not pass the route-source-content
assertions on the dev file specifically.

**TG-3 (lines 251-267) — dev Cedar policy file is valid and
channel-derived.** Asserts
`policy/cedar/channels/dev/services/server-manager-api/policies.json`
parses as JSON, contains both `public-intake-allow` and
`public-intake-no-read` Cedar statements, both use
`Public::"web-intake.dev"`, and neither uses
`Public::"web-intake.local"`.

The one degradation path: TG-3 lines 265-267 says "If a local
Cedar parser or policy materializer is available in the
implementation environment, run it against the two new
statements. If not, the static literal checks above are the
required CI guard for this manifest-authoring slice." This is
graceful degradation around a tooling constraint, not a "trust
local" placeholder — the static literal checks (presence of both
policy ids, channel-derived principal, absence of local
principal) are the CI guard either way, with the Cedar parse
upgrade applied if available. Flagged but not a shortcut.

**TG-4 (lines 270-282) — dev kustomization builds.** As detailed
in C4, runs `kustomize build gitops/channels/dev/` and asserts
the three real manifests appear in the output.

**TG-5 (lines 284-298) — no channel-local hardcodes leak into
dev manifests.** Regex sweep over `gitops/channels/dev/` and the
dev Cedar policy file:

> - no `*.local.humility.local` hosts;
> - no `web-intake.local`;
> - no `/auth/local/`, `/postgres/local/`, `/object-storage/local/`,
>   or `/runtime/local` paths;
> - no local Step CA issuer annotations or local ingress TLS
>   secret names;
> - no `policy/cedar/channels/local` references.

with the explicit carve-out that `.svc.cluster.local` is allowed
because "that string is not the Humility channel id." This sweep
runs over the dev directory specifically, not the local one — a
"trust local" placeholder that re-validates only `gitops/channels/local/`
would not catch local hardcodes leaking into dev.

The "trust local" version of the test plan would require **all**
of TG-1 through TG-5 to bind against `gitops/channels/local/`
or the existing local Cedar policies. None of them do. Each
test group names dev-specific files, dev-specific hostnames,
dev-specific principal, and dev-specific paths.

**Risk:** the shortcut would be (a) re-run the existing
BL-013 tripwire and assert "still passes for local" without
adding any dev-specific assertion, so a missing dev manifest
silently passes because the tripwire's channel-discovery short-
circuits when the dev directory is absent, (b) parse the dev
Pomerium manifest only at the YAML root and not the embedded
`config.yaml` so a stub config-yaml passes, or (c) write the
TG-5 regex sweep over both `local/` and `dev/` so local channel
hits don't trigger a failure even when dev contains them.

**Mitigation:** TG-1 explicitly asserts `discover_channels()`
returns `dev` (not just "passes for whatever channels exist")
and `verify_substrate("dev")` returns no failures; TG-2 parses
the embedded `managedSecretReference.template.data.config.yaml`
not just the outer manifest; TG-3 asserts both policy ids and
both channel-derived principal cases on the dev file
specifically; TG-5's regex sweep is scoped to
`gitops/channels/dev/` and the dev Cedar policy file
specifically; TG-4 asserts dev-specific build output content.

**Verdict:** Not a shortcut. The Cedar parser fallback in TG-3
is a documented graceful degradation around tooling
availability, with static literal checks as the binding CI
guard — not a placeholder.

## Verdict reasoning

INIT-138 ships exactly the contour the gate watches for:

- Channel-derived hostnames are real, fixed, and grounded in
  `infra/channels/dev.yaml`'s `ingress.remote_domain: humility.gg`
  plus the existing dev access-policy issuer convention. The
  full table (`api.dev.humility.gg`, `web.dev.humility.gg`,
  `protected-api.dev.humility.gg`, `https://authenticate.dev.humility.gg`,
  `https://auth.dev.humility.gg/application/o/pomerium/`,
  `Public::"web-intake.dev"`) is locked at the proposal level
  and bans the local equivalents from appearing in dev
  manifests.

- All four substrate items have field-level contracts: the
  top-level `kustomization.yaml` references three real manifest
  files; the API-side rate-limit ingress lists kind, namespace,
  host, paths, backend, and the Step-CA-annotation ban; the
  Pomerium-side rate-limit ingress lists kind, namespace, host,
  paths, backend, and the Step-CA-annotation ban; the Pomerium
  config-bearing manifest lists embedded route sources, route
  ordering, public catch-all upstream, dev authenticate URL,
  dev IdP provider URL, and the explicit anti-scope around
  runtime Infisical secret sourcing.

- Both Cedar policies ship in this slice with full inline
  bodies: `public-intake-allow` (`permit` for
  `Public::"web-intake.dev"` to `application:submit_public`)
  and `public-intake-no-read` (`forbid` for the same principal
  on `api:read`). The forbid is not deferred to a follow-up,
  the principal is the dev channel-derived public principal
  (not the local one), and a service-identity entry for the
  public principal is explicitly forbidden.

- Kustomize wiring is real: the top-level
  `gitops/channels/dev/kustomization.yaml` references the three
  manifest files directly, and TG-4's acceptance asserts each
  manifest appears in `kustomize build` output (not just a
  clean exit code). The narrow scoping to a top-level
  kustomization without intermediate kustomizations is
  deliberate (don't imply the rest of the dev channel exists),
  not a "skip wiring for now" stub.

- Tests bind against the new dev manifests at five layers:
  the BL-013 tripwire (channel discovery + substrate
  verification on `dev`), the Pomerium embedded config parser
  (route block contents and route source values), the dev
  Cedar policy file (both policy ids + channel-derived
  principal + absence of local principal), the dev kustomize
  build (output content presence), and the dev-scoped local-
  hardcode regex sweep. None of the test groups defer to
  "trust local" placeholders. The TG-3 Cedar-parser fallback
  is a documented graceful degradation around tooling
  availability, with static literal checks as the binding CI
  guard either way.

- Anti-scope (proposal lines 300-319) explicitly forbids
  template/refactor systems, dual-host support, fallback
  principals, feature flags, deprecated aliases, compatibility
  shims, and modifications to local channel manifests. The
  diff budget (§6, lines 321-345) lists exactly the four
  GitOps additions, the policy file modification, and "prefer
  zero test-file changes" — no production API, daemon, web
  app, migration, generated client, runtime script, local
  manifest, or deployment code changes are budgeted.

**Implementation note (not a proposal-level shortcut) to lock
at slice landing:**

1. **Cedar parser path probe.** TG-3 lines 265-267 says "If a
   local Cedar parser or policy materializer is available in
   the implementation environment, run it against the two new
   statements." Implementation should attempt to discover
   whether `cedar` (CLI or Python binding) is available in the
   CI environment and, if so, wire the parser-backed assertion
   in addition to the static literal checks. If not available,
   the static literal checks remain the binding CI guard. This
   is a tooling-availability concern at the implementation
   boundary, not a proposal-level shortcut.

The proposal itself ships the full narrow public-intake substrate
this slice needs, with channel-derived values, both Cedar policy
halves, real kustomize wiring, and dev-bound test coverage.

Verdict: LOW.

SHORTCUT_DONE: plans/risk/init-138-shortcut.md
