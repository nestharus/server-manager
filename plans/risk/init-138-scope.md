# INIT-138 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/33-init-138-remote-channel-public-intake.md`
- `research/48-init-138-remote-channel-problem-map.md`

## Findings

### 1. Only 3-5 new files under gitops/channels/dev/ + policy/cedar/channels/dev/ — PASS

Proposal §3 "New files" enumerates exactly four new manifests, all under
`gitops/channels/dev/`:

- `gitops/channels/dev/kustomization.yaml`
- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`

§3 "Modified files" lists exactly one existing file under
`policy/cedar/channels/dev/`:

- `policy/cedar/channels/dev/services/server-manager-api/policies.json`,
  appended with the two canonical policy IDs `public-intake-allow` and
  `public-intake-no-read`.

Total change surface is five files, both directories scoped exactly as
the gate requires. §6 diff budget restates the same five entries and
adds no others. §2 Q5 explicitly forbids intermediate kustomizations
(`applications/`, `applications/server-manager/`, `auth/`,
`auth/pomerium/`), keeping the file count from drifting upward via
incidental wiring. Test diff is "prefer zero test-file changes" with at
most focused assertions on the existing
`infra/tests/test_public_intake_channel_tripwire.py` if a missing
channel-derived check is uncovered — that is gate-compatible because it
does not enlarge the manifest/policy surface.

### 2. No production code changes — PASS

§5 anti-scope explicitly excludes every production surface: "Do not
port other subsystems: Authentik, MinIO/object-storage runtime,
Postgres CNPG, Atlas, OPAL, Pomerium proxy deployment, server-manager
API/web deployments, Buildkite, app-clusters, tenant isolation,
observability, or security policies beyond the public-intake route
block and Cedar policy pair."

§6 diff budget reinforces the same prohibition: "No production API,
Discord daemon, web app, migration, generated client, runtime script,
local manifest, or deployment code changes are budgeted." The narrow
intent is repeated in §1: "This is not a full remote runtime, a full
channel template, or a Vultr apply."

The change surface is manifest authoring plus a Cedar policy append.
No service code, daemon, migration, generator, runtime script, or
deployment workflow is touched.

### 3. No template-system refactor (no Option C) — PASS

§5 anti-scope blocks Option C directly: "Do not introduce a channel
templating refactor, Kustomize base/overlay system, renderer changes,
compatibility shims, feature flags, deprecated aliases, dual-host
support, or fallback principals."

§1 locks the slice to Option A: "The scope is the problem-map Option A:
materialize only the `dev` public-intake substrate required by BL-013,
using channel-derived hosts and principals." §2 Q1 repeats the lock:
"Lock Option A: narrow public-intake-only port for `dev`. The
implementation must create the smallest `gitops/channels/dev/`
substrate that lets static CI validate the same logical public-intake
surface already present in `local`. Do not copy the whole local
channel and do not introduce a template/refactor system in this
slice." §2 Q5 forbids intermediate kustomizations that would seed an
overlay structure.

The research recommendation (research §"Recommendation") matches:
"Land Option A first… Option C is a good later design direction if
multiple remote channels begin to repeat the same files. It should not
be the first INIT-138 implementation." No base/overlay hierarchy,
renderer rewrite, or templated parameter system is authorized.

### 4. No Vultr/Flux/DNS/cert work — PASS

§5 anti-scope is explicit on all four: "Do not apply anything to
Vultr, Flux, Kubernetes, DNS, or certificate issuers. This proposal
is manifest authoring and static validation only." The follow-on
sentence enumerates the specific runtime surfaces that stay
untouched: "Do not add dev Flux wiring, a dev `gitops` contract
block, remote Git source rendering, SOPS bootstrap, Cloudflare
records, ACME issuer materialization, or load balancer
verification."

§3 reinforces this at the manifest level: the new API ingress and
Pomerium ingress files must carry "No local Step CA annotations or
local TLS secret names", and the Pomerium config-bearing manifest
must avoid local-only `insecure_server`/`grpc_insecure` while
keeping "No invented dev Infisical runtime contract" — runtime
secret sourcing remains explicitly anti-scope. §4 TG-4 only requires
`kustomize build gitops/channels/dev/` exits successfully; it does
not require a cluster apply, Flux reconciliation, DNS resolution,
or certificate issuance.

No Vultr provider claim, Flux `GitRepository`/`Kustomization`, DNS
record, ACME issuer, or TLS secret material is authorized.

### 5. Other subsystems (Authentik, MinIO, Postgres, OPAL) untouched for dev — PASS

§5 anti-scope names every subsystem the gate calls out, plus
adjacent ones, and bars them all: "Do not port other subsystems:
Authentik, MinIO/object-storage runtime, Postgres CNPG, Atlas,
OPAL, Pomerium proxy deployment, server-manager API/web
deployments, Buildkite, app-clusters, tenant isolation,
observability, or security policies beyond the public-intake route
block and Cedar policy pair." Authentik, MinIO, Postgres (CNPG),
and OPAL are each explicitly enumerated.

§3 confines the Pomerium work to a single config-bearing manifest
that exists "so the BL-013 parser can validate the route block",
not as a Pomerium proxy deployment, and bars dev Infisical runtime
contract authoring. The Cedar work is scoped to appending two
public-intake entries to the existing dev policies file, leaving
"existing dev user, Buildkite, and Crossplane policies" preserved.

Research §"Channel-parameterized variables" makes the cross-system
surface visible (object storage, image registry, Authentik OIDC
endpoints, OPAL bundles, CNPG backup destinations, observability
buckets), and the proposal's lock on Option A intentionally
defers all of it. No manifest under `gitops/channels/dev/` outside
`applications/server-manager/public-intake-rate-limit.yaml` and
`auth/pomerium/...` is authorized in this slice.

## Conclusion

The proposal authorizes exactly five files (four new manifests
under `gitops/channels/dev/` plus a Cedar policy append under
`policy/cedar/channels/dev/`), explicitly forbids production code
changes, locks Option A and bars Option C's templating/overlay
refactor, anti-scopes Vultr/Flux/DNS/certificate work, and lists
Authentik, MinIO, Postgres CNPG, and OPAL among the subsystems
that must remain untouched for dev. Each gate check is satisfied
by an explicit proposal section. Scope risk is acceptable.

SCOPE_DONE: plans/risk/init-138-scope.md
