# INIT-138 — Supported-surface risk gate

**Verdict:** LOW

INIT-138 (Option A: narrow public-intake-only port for `dev`)
materializes the smallest `gitops/channels/dev/` manifest
substrate that lets the BL-013 static tripwire validate the
same logical public-intake surface that already exists for
`local`, using channel-derived hosts and a channel-derived
public principal. The slice ships purely as new files under
`gitops/channels/dev/...` and a two-policy append to the
existing `policy/cedar/channels/dev/services/server-manager-api/policies.json`.
Every other repository surface — `services/api/`,
`services/web/`, Alembic heads, `Settings`, all
`gitops/channels/local/...` manifests, `infra/channels/*.yaml`,
the `infra/scripts/render-gitops-source.py` renderer, the
BL-013 tripwire test source itself, and every other channel-
contract / runtime surface — is preserved verbatim per
proposal §5 Anti-scope and §6 Diff Budget. The slice is
intentionally a manifest-authoring + static-validation port,
not a remote runtime, not a channel-templating refactor, and
not a Vultr apply.

## Surfaces touched

### 1. No public API change

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/api/app/api/v1/endpoints/...` route set | post-INIT-137 set (`/api/v1/public/applications`, `/api/v1/public/applications/upload-url`, `/api/v1/public/chapters`, plus authenticated routes) | unchanged — proposal §6 budgets zero changes to `services/api/`; the dev manifest substrate references existing service names (`server-manager-api:8000`, `pomerium-proxy:80`, `server-manager-web.web.svc.cluster.local:8080`) without modifying any handler, request model, response model, dependency, or error mapper | **none** |
| `PublicApplicationSubmission` / `PublicApplicationSubmissionReceipt` contracts | post-INIT-137 set (`services/api/app/contracts/applications.py`) | unchanged — INIT-138 adds no contract, no schema, no Pydantic field | **none** |
| Public chapters endpoint | unchanged (`services/api/app/api/v1/endpoints/public_chapters.py`) | unchanged — the dev Pomerium and Kong ingresses reference the same logical paths (`/api/public/chapters`, `/api/v1/public/chapters`) but on `web.dev.humility.gg` / `api.dev.humility.gg`; no API code change is required to serve them | **none** |
| Auth dependencies / receipt chain | post-INIT-137 set (`verify_applicant_receipt`, `authorize_public_intake`) | unchanged — Cedar dev policies are appended only; the existing `authorize_public_intake` decision logic resolves on principal id, and the new `Public::"web-intake.dev"` principal is selected by deployment channel, not by code change | **none** |

Risk on §1: **none**. No FastAPI route, request model,
response model, dependency, error mapper, service module, or
contract is touched. The slice is manifest-only.

### 2. No env vars / migrations / production code changes

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `Settings` class | post-INIT-137 set (`services/api/app/core/settings.py`) | unchanged — proposal §6 budgets zero source changes; no new env key, no rename, no SecretStr field | **none** |
| Alembic head | post-INIT-137 head (`migrations/versions/`) | unchanged — proposal §6 explicitly excludes "migration" from the diff budget; `form_definitions.fields` and `applications.responses` JSONB columns are not touched | **none** |
| `services/api/pyproject.toml` deps | post-INIT-137 set | unchanged — no new wheel, no version bump | **none** |
| `services/web/` SPA | post-INIT-137 / post-SLICE-030 set | unchanged — proposal §5 anti-scope covers "server-manager API/web deployments" and the diff budget does not list any web file | **none** |
| Discord daemon, generated client, runtime scripts | unchanged | unchanged — proposal §6 explicitly excludes "Discord daemon, web app, migration, generated client, runtime script" from the budget | **none** |
| InfisicalSecret runtime contract for dev | undefined (dev channel `infra/channels/dev.yaml` deliberately omits `infisical`, `auth_stack`) | the new `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml` is authored as a Pomerium config-bearing manifest sufficient for static parsing only; proposal §3 explicitly states "No invented dev Infisical runtime contract. … only the route template is in scope for static validation; runtime secret sourcing remains anti-scope until a dev `auth_stack`/Infisical contract exists." | **none** for this slice — manifest exists for static parse only; no runtime is implied. Anyone reading the dev manifest as "runtime-ready" is corrected by proposal §1 ("not a runnable remote server-manager deployment") and §5 anti-scope |

Risk on §2: **none**. Zero source changes in `services/api/`,
`services/web/`, `migrations/`, `infra/scripts/`, or any
other production code path. Zero env-var redefinition. The
`InfisicalSecret` document under `gitops/channels/dev/auth/pomerium/`
is a static config carrier for the BL-013 parser, not a
runtime secret-sourcing contract.

### 3. Existing local channel untouched

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml` | post-INIT-135 set | unchanged — proposal §5 "Do not modify any local channel manifest. The local channel remains the reference implementation for this narrow port." | **none** |
| `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` | post-INIT-135 set | unchanged | **none** |
| `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml` | post-INIT-127 / INIT-134 / INIT-135 / INIT-136 / INIT-137 set | unchanged | **none** |
| `policy/cedar/channels/local/services/server-manager-api/policies.json` | post-INIT-135 set with `public-intake-allow` and `public-intake-no-read` for `Public::"web-intake.local"` | unchanged | **none** |
| Every other `gitops/channels/local/...` file (232 files per the problem map) | unchanged | unchanged — proposal §6 budgets zero local manifest edits | **none** |
| Channel templating / Kustomize base/overlay system | none (problem map confirms "There is no `gitops/channels/_template/`, no `gitops/channels/base`, and no Kustomize overlay hierarchy") | unchanged — proposal §5 explicitly forbids "channel templating refactor, Kustomize base/overlay system, renderer changes, compatibility shims, feature flags, deprecated aliases, dual-host support, or fallback principals" | **none** — Option A is intentionally a direct authoring of dev files, not a refactor of local |

Risk on §3: **none**. The local channel is the reference
implementation and is not edited. Option A's diff is purely
additive under `gitops/channels/dev/...` and a 2-object
append to `policy/cedar/channels/dev/services/server-manager-api/policies.json`.
The renderer (`infra/scripts/render-gitops-source.py`) is not
touched, so its existing local-only Cedar paths and snapshot
behavior remain intact.

### 4. BL-013 tripwire still passes for local + now for dev

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `infra/tests/test_public_intake_channel_tripwire.py` source | static tripwire that discovers non-local channels via `gitops/channels/<channel>/applications/server-manager` containing public-intake-relevant material, then validates channel-derived hosts (`api.<channel>.humility.gg`, `web.<channel>.humility.gg`), Cedar `Public::"web-intake.<channel>"`, Pomerium route ordering, and Kong/web ingress paths | unchanged — proposal §3 / §6 say "Prefer zero test-file changes" and "No change should be required" | **none** for the test source |
| `discover_channels()` behavior for `local` | explicitly skipped (`if channel_dir.name == "local": continue` at `infra/tests/test_public_intake_channel_tripwire.py:124-125`) | unchanged — discovery still skips local; the tripwire never asserts local. The "passes for local" check on the gate is met because the local channel is not in the tripwire's validation set and remains entirely untouched (per §3 above), so no regression is possible | **none** — note: the tripwire's contract is "non-local channels with public-intake material must be channel-derived." Local is the reference; it is not asserted by the tripwire and cannot regress |
| `discover_channels()` behavior for `dev` | returns `[]` (no `gitops/channels/dev/` exists today) | returns `["dev"]` once the new `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml` lands. `_is_public_intake_relevant` triggers on either filename match (`public-intake-rate-limit.yaml`) or trigger-name match (`server-manager-public-intake-api`, `web-public-intake`, `public-intake-rate-limit`) or trigger-path match in an Ingress; the dev manifest matches all three signals | **none** — discovery is channel-derived (folder naming convention), not channel-hardcoded |
| `verify_substrate("dev")` behavior | currently never called (channel not discovered) | returns `[]` after the slice lands. All four validators pass:<br>• `_validate_api_rate_limit`: dev API ingress on `api.dev.humility.gg` with paths `/api/v1/public/applications` and `/api/v1/public/chapters`, backend `server-manager-api:8000`, plugin annotation `konghq.com/plugins: public-intake-rate-limit`, KongPlugin `public-intake-rate-limit` in namespace `server-manager`<br>• `_validate_pomerium_rate_limit`: dev web ingress on `web.dev.humility.gg` with paths `/api/public/applications`, `/api/public/chapters`, `/api/applications`, backend `pomerium-proxy:80`, plugin annotation present, namespace `auth-system`<br>• `_validate_cedar_policies`: `public-intake-allow` and `public-intake-no-read` exist in the dev policy file with `Public::"web-intake.dev"`, the canonical effects, and the canonical action/resource literals; `Public::"web-intake.local"` is absent (the tripwire explicitly fails if a non-local channel content contains the local principal at `infra/tests/test_public_intake_channel_tripwire.py:305-308`)<br>• `_validate_pomerium_routes`: dev Pomerium config-bearing manifest parses, embedded `config.yaml` parses, has a `routes` list, identity-bearing routes for `https://web.dev.humility.gg` precede the public catch-all to `http://server-manager-web.web.svc.cluster.local:8080` | **none** — every check is channel-derived. Proposal §2 Q2 locks the exact host strings and principal name; proposal §3 / §4 lock the exact ingress paths, backend names, and ports; proposal §2 Q4 locks the route ordering rule |
| `test_repository_state_passes()` | passes today (no non-local channel exists, so the loop is empty) | passes after the slice — `discover_channels` returns `["dev"]`, `verify_substrate("dev")` returns `[]`, the `assert failures == []` holds | **none** |
| `test_partial_synthetic_channel_fails()` and `test_full_synthetic_channel_passes()` | tmp-path synthetic tests | unchanged — they construct synthetic substrates under `tmp_path` and do not depend on real `gitops/channels/dev/` content | **none** |

Risk on §4: **none**. The tripwire test source is not
modified; the dev manifest substrate is authored to satisfy
every channel-derived check the tripwire performs. Local
remains the reference implementation and is not in the
tripwire's validation set, so it cannot regress from this
slice. Proposal §3 explicitly contemplates extending the
tripwire only "if implementation reveals that discovery or
validation is not channel-derived enough for the real dev
files" and forbids weakening the tripwire to accommodate
partial materialization.

### 5. No DNS/cert/runtime assumption baked in (channel-derived only)

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Hostnames in dev manifests | n/a | `api.dev.humility.gg`, `web.dev.humility.gg`, `protected-api.dev.humility.gg`, `https://authenticate.dev.humility.gg`, `https://auth.dev.humility.gg/application/o/pomerium/` — all derived from `infra/channels/dev.yaml` `ingress.remote_domain: humility.gg` plus the channel id `dev`, matching the existing dev access-policy issuer convention `https://auth.dev.humility.gg/application/o/humility-service-identities/` | **none** — all hosts are `<role>.<channel>.<remote_domain>`, the same pattern BL-013's tripwire validates as channel-derived |
| Public principal | n/a | `Public::"web-intake.dev"` — derived from channel id, matches the `Public::"web-intake.<channel>"` pattern enforced at `infra/tests/test_public_intake_channel_tripwire.py:281` | **none** |
| TLS issuers / Step CA / cert annotations | local uses `humility-local-step-ca`, `StepClusterIssuer`, `*-local-ingress-tls` | absent from dev manifests — proposal §3 mandates "No local Step CA annotations or local TLS secret names" on both the API and Pomerium-side dev ingresses. The dev channel does not bake in an ACME issuer or Cloudflare DNS record either; remote TLS / DNS contracts remain a follow-up initiative | **none** — the slice intentionally omits TLS/DNS materialization. Proposal §5 anti-scope: "Do not apply anything to Vultr, Flux, Kubernetes, DNS, or certificate issuers" |
| Kong rate-limit policy mode | local KongPlugin uses `policy: local` | proposal §3 explicitly omits the `policy` field for the dev static slice "unless a later runtime proposal chooses a remote rate-limit backend" — channel-derived, not local-baked | **none** |
| Pomerium `insecure_server` / `grpc_insecure` | local `secrets-infisicalsecret.yaml` uses these all-in-one settings | absent from dev manifest per proposal §3 "No local-only `insecure_server` or `grpc_insecure` settings" | **none** |
| In-cluster service DNS (`server-manager-web.web.svc.cluster.local:8080`) | local catch-all upstream | reused unchanged in dev catch-all upstream — proposal §2 Q2 explicitly notes "Internal Kubernetes service DNS such as `server-manager-web.web.svc.cluster.local` is not a channel hard-code and remains allowed where Pomerium needs an in-cluster upstream." The BL-013 tripwire also expects this exact upstream string at `infra/tests/test_public_intake_channel_tripwire.py:33` (`WEB_UPSTREAM`) | **none** — `.svc.cluster.local` is the Kubernetes internal DNS suffix, not the Humility channel id `local`. The proposal §4 TG-5 sweep is explicit that this must not be rejected |
| Image refs / registry | local uses `k3d-humility-local:5000/local/...:init-*-local`; dev `image_registry` is `ewr.vultrcr.com/humility` with prefix `dev` | absent from dev manifests in this slice — Option A does not deploy server-manager workloads. The dev ingresses reference Service names (`server-manager-api:8000`, `pomerium-proxy:80`) without backing Deployments. Proposal §1 explicitly says "It may be valid for static manifest checks and future runtime work, but it must not be described as a runnable remote server-manager deployment." | **none** for this slice — anti-scope covers "Authentik, MinIO/object-storage runtime, Postgres CNPG, Atlas, OPAL, Pomerium proxy deployment, server-manager API/web deployments" |
| Flux / GitOps wiring for dev | `infra/channels/dev.yaml` deliberately omits `gitops` | unchanged — proposal §5 anti-scope covers "dev Flux wiring, a dev `gitops` contract block, remote Git source rendering, SOPS bootstrap, Cloudflare records, ACME issuer materialization, or load balancer verification". The `infra/scripts/render-gitops-source.py` requirement that a resolved `gitops` block exists remains; this slice does not attempt to render dev | **none** — render path is untouched; dev manifests are static-checked only via the BL-013 tripwire and `kustomize build gitops/channels/dev/` (TG-4) |
| Kustomization wiring | n/a for dev | new `gitops/channels/dev/kustomization.yaml` references only the three dev public-intake manifest files directly, no intermediate `applications/` or `auth/` kustomizations — keeps the diff small and avoids implying that the rest of the dev channel exists. `kustomize build` should succeed for the narrow public-intake substrate (TG-4) | **none** |

Risk on §5: **none**. Every dev-channel value is derived
from `infra/channels/dev.yaml` plus the channel id `dev`, or
from explicitly-allowed Kubernetes-internal substrates
(`.svc.cluster.local` upstreams, Service names like
`server-manager-api:8000` / `pomerium-proxy:80` that resolve
within any cluster). No DNS, cert issuer, image registry,
load-balancer, Flux source, or runtime secret backend is
materialized. Proposal §4 TG-5's regex sweep is the
guardrail against accidental local-host or local-policy-path
leakage into the dev tree.

## Verdict reasoning

LOW.

1. **No public API change (gate §1)**: zero `services/api/`
   handler, contract, dependency, or error-mapper edits.
   The new dev ingresses reference existing in-cluster
   Service names and public path prefixes that already
   exist behind the local channel's API; no new HTTP shape
   is introduced anywhere.
2. **No env vars / migrations / production code (gate §2)**:
   `Settings`, Alembic head, `services/api/pyproject.toml`,
   `services/web/`, the Discord daemon, generated clients,
   and runtime scripts are all unchanged. The InfisicalSecret
   document under `gitops/channels/dev/auth/pomerium/` is
   authored as a static carrier for the BL-013 Pomerium
   config parser only; runtime secret sourcing for dev
   remains anti-scope per proposal §3.
3. **Existing local channel untouched (gate §3)**: proposal
   §5 explicitly forbids modifying any local manifest, and
   §6's diff budget enumerates only four new files under
   `gitops/channels/dev/...` plus a 2-object append to the
   existing dev Cedar policies file. The renderer is not
   touched, so its hardcoded local Cedar paths remain
   intact and the local snapshot output remains stable.
4. **BL-013 tripwire still passes for local + now for dev
   (gate §4)**: the tripwire test source is unchanged; its
   `discover_channels` skips local entirely (so local cannot
   regress from this slice) and discovers dev once the new
   API-side manifest exists. `verify_substrate("dev")` is
   designed to return `[]` because every channel-derived
   property the tripwire validates (host, principal, paths,
   backend, route ordering) is locked in proposal §2 / §3 /
   §4 to the exact strings the validators look for.
   `test_repository_state_passes()` and the two synthetic
   `tmp_path` tests all continue to hold.
5. **No DNS/cert/runtime assumption baked in — channel-
   derived only (gate §5)**: every dev value derives from
   `infra/channels/dev.yaml` `ingress.remote_domain:
   humility.gg` plus the channel id `dev`. No Step CA, no
   ACME issuer, no Cloudflare record, no Vultr Object
   Storage block, no Vultr Container Registry image ref,
   no Flux source, no rate-limit policy backend baked in.
   The only non-channel-derived strings allowed are the
   Kubernetes internal DNS upstream and in-cluster Service
   names, both of which the proposal calls out as
   intentional and the tripwire's TG-5 regex sweep
   intentionally allows.

This is a manifest-authoring + static-validation slice. It
is intentionally partial: it produces a dev public-intake
substrate that satisfies the BL-013 tripwire and
`kustomize build gitops/channels/dev/`, but it does not
imply a runnable remote server-manager deployment. Full
remote runtime (image refs, runtime secret paths, ACME/DNS,
Flux wiring, MinIO-to-Vultr migration, app-cluster
provisioning, Authentik/Pomerium runtime deployment, server-
manager API/web deployment) is documented as anti-scope and
remains follow-up initiative work.

Verdict: **LOW**.

## Findings

None. All five supported-surface gate criteria pass:

1. ✓ **No public API change** — zero `services/api/`
   handler, contract, request/response model, dependency,
   or error-mapper edit. The dev ingresses reference
   existing in-cluster Service names (`server-manager-api:8000`,
   `pomerium-proxy:80`) and existing public path prefixes
   (`/api/v1/public/applications`, `/api/v1/public/chapters`,
   `/api/public/applications`, `/api/public/chapters`,
   `/api/applications`); no new HTTP shape or new path is
   introduced.
2. ✓ **No env vars / migrations / production code changes** —
   `services/api/app/core/settings.py`, `migrations/`,
   `services/api/pyproject.toml`, `services/web/`, the
   Discord daemon, generated clients, and runtime scripts
   are all unchanged per proposal §6 diff budget. The
   `InfisicalSecret` document in
   `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`
   is a static config carrier for the BL-013 Pomerium
   config parser; runtime secret sourcing remains anti-
   scope (proposal §3).
3. ✓ **Existing local channel untouched** — proposal §5
   forbids modifying any local manifest; §6 diff budget
   lists only four new files under `gitops/channels/dev/...`
   plus a 2-object append to the existing
   `policy/cedar/channels/dev/services/server-manager-api/policies.json`.
   `infra/scripts/render-gitops-source.py` is not touched.
4. ✓ **BL-013 tripwire still passes for local + now for
   dev** — tripwire source
   (`infra/tests/test_public_intake_channel_tripwire.py`)
   is unchanged. `discover_channels()` skips local
   entirely (line 124-125), so local is not in the
   tripwire's assertion set and cannot regress from this
   slice. After the slice, `discover_channels()` returns
   `["dev"]` and `verify_substrate("dev")` returns `[]`
   because every channel-derived check (`api.dev.humility.gg`,
   `web.dev.humility.gg`, `Public::"web-intake.dev"`, the
   canonical Cedar action/resource literals, the
   `pomerium-proxy:80` and `server-manager-api:8000`
   backends, the `WEB_UPSTREAM`
   `http://server-manager-web.web.svc.cluster.local:8080`
   catch-all, and identity-route-before-public-catch-all
   ordering) is locked by proposal §2 Q2 / §2 Q4 / §3 / §4.
5. ✓ **No DNS/cert/runtime assumption baked in (channel-
   derived only)** — every dev value derives from
   `infra/channels/dev.yaml` `ingress.remote_domain:
   humility.gg` plus channel id `dev`. No Step CA, no ACME
   issuer, no Cloudflare/external-dns record, no Vultr
   Object Storage block, no Vultr Container Registry image
   ref, no Flux GitRepository/Kustomization, no rate-limit
   policy backend. Kong `KongPlugin/public-intake-rate-limit`
   omits the `policy` field rather than baking in a local
   choice. Pomerium dev manifest omits `insecure_server`
   and `grpc_insecure`. The only non-channel-derived
   strings are `.svc.cluster.local` upstreams and in-
   cluster Service names, which proposal §2 Q2 explicitly
   allows and the BL-013 tripwire's TG-5 regex sweep
   explicitly tolerates.

SUPPORTED_SURFACE_DONE: plans/risk/init-138-supported-surface.md
