# INIT-138 Hookpoints — Remote channel public-intake substrate (dev)

Scope per Proposal 33 + research 48 Option A: materialize the
narrowest `gitops/channels/dev/` substrate that satisfies the
BL-013 tripwire (`infra/tests/test_public_intake_channel_tripwire.py`),
plus a 2-policy append to the existing dev Cedar policies file. No
local channel edits, no production code, no Vultr/Flux/DNS/cert
materialization, no template/overlay refactor.

`gitops/channels/dev/` does not exist today (verified
`ls gitops/channels/` → only `local/`); H1, H2, H3 and H5 are all
new files. H4 is an append to an existing file. H6 is a "no test
edit expected" hook with one bounded extension contract.

## Channel-derived value substitution table

The Q2 lock (proposal lines 52-62) defines exactly six string
substitutions from local → dev. Every dev manifest below applies a
subset of this table:

| Token | Local value | Dev value (substitution) | Source of derivation |
|---|---|---|---|
| API hostname | `api.local.humility.local` | `api.dev.humility.gg` | `<role>.<channel>.<remote_domain>` from `infra/channels/dev.yaml` `ingress.remote_domain: humility.gg` |
| Web hostname | `web.local.humility.local` | `web.dev.humility.gg` | same pattern |
| Protected API hostname | `protected-api.local.humility.local` | `protected-api.dev.humility.gg` | same pattern |
| Authenticate URL | `https://authenticate.local.humility.local` | `https://authenticate.dev.humility.gg` | same pattern |
| IdP provider URL | `https://auth.local.humility.local/application/o/pomerium/` | `https://auth.dev.humility.gg/application/o/pomerium/` | matches existing dev access-policy issuer host `auth.dev.humility.gg` (`policy/cedar/channels/dev/services/server-manager-api/service-identities.json:2`) |
| Public Cedar principal | `Public::"web-intake.local"` | `Public::"web-intake.dev"` | `Public::"web-intake.<channel>"` pattern enforced by tripwire at `infra/tests/test_public_intake_channel_tripwire.py:281` |

Locally-baked strings that MUST be dropped (not substituted) for
dev (per Q2 lines 70-75 + §3 lines 162-196):

- `cert-manager.io/issuer: humility-local-step-ca`
- `cert-manager.io/issuer-kind: StepClusterIssuer`
- `cert-manager.io/issuer-group: certmanager.step.sm`
- `secretName: server-manager-api-local-ingress-tls`
- `secretName: web-local-ingress-tls`
- `config.policy: local` (KongPlugin field — omit for dev)
- `insecure_server: true` (Pomerium all-in-one local mode)
- `grpc_insecure: true` (Pomerium all-in-one local mode)
- `envSlug: local`
- `secretsPath: /auth/local/pomerium`
- (Any `hostAPI: http://infisical...` — dev has no `auth_stack`/Infisical
  contract; runtime secret sourcing remains anti-scope per §3 lines
  192-196.)

Allowed cross-channel constants (NOT subject to substitution):

- Kubernetes-internal upstream `http://server-manager-web.web.svc.cluster.local:8080`
  (matches `WEB_UPSTREAM` at `infra/tests/test_public_intake_channel_tripwire.py:33`).
- Kubernetes-internal upstream `http://server-manager-api.server-manager.svc.cluster.local:8000`
  (used by local `/auth/discord/` + `protected-api` routes).
- Service backend `server-manager-api` port `8000`.
- Service backend `pomerium-proxy` port `80`.
- Namespace `server-manager` (KongPlugin + API Ingress).
- Namespace `auth-system` (web Ingress + Pomerium config-bearing manifest).
- KongPlugin name `public-intake-rate-limit`.
- Ingress names `server-manager-public-intake-api`, `web-public-intake`.
- Annotation `konghq.com/plugins: public-intake-rate-limit`.
- `ingressClassName: kong`.
- `pathType: Prefix`.

## H1 — server-manager-side rate-limit YAML

**Local source (read-only reference):**
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
(51 lines; verbatim contents above).

| Local span | Resource fragment | Dev disposition |
|---|---|---|
| Lines 1-13 | `KongPlugin/public-intake-rate-limit` in namespace `server-manager`, plugin `rate-limiting`, config `minute: 5`, `hour: 50`, **`policy: local` (line 10)**, `fault_tolerant: true`, `hide_client_headers: false` | **Carry verbatim except line 10**: omit `policy: local` per Q4 line 172. KongPlugin name + namespace are channel-invariant (tripwire `_validate_api_rate_limit` requires `KongPlugin` named `public-intake-rate-limit` in namespace `server-manager`, lines 215-217). `fault_tolerant` and `hide_client_headers` are not validated by the tripwire and may be carried as-is. |
| Lines 14-26 | Ingress metadata (name `server-manager-public-intake-api`, namespace `server-manager`, labels, annotations) | **Drop the three Step CA annotation lines (23-25)**. Keep `konghq.com/plugins: public-intake-rate-limit` (line 26) — required by tripwire `_validate_ingress_paths` line 173. The `app.kubernetes.io/name: server-manager-api` label and the `platform.humility.gg/init` label are not validated and may be dropped or carried; recommend dropping the `init` label since it embeds local-channel slice provenance. |
| Lines 27-32 | `spec.ingressClassName: kong` (line 28) + TLS block (lines 29-32) — host `api.local.humility.local`, secretName `server-manager-api-local-ingress-tls` | **Drop the entire TLS block (lines 29-32)** per §3 line 171 ("No local Step CA annotations or local TLS secret names"). `ingressClassName: kong` may be carried; the tripwire does not assert it. |
| Lines 33-50 | Rules: host `api.local.humility.local` (line 34); paths `/api/v1/public/applications` (line 37) and `/api/v1/public/chapters` (line 44); each backend `service.name: server-manager-api`, `service.port.number: 8000` (lines 41-43, 48-50) | **Substitute host → `api.dev.humility.gg` (line 34)**. Keep paths verbatim (validated by `API_PUBLIC_PATHS = {"/api/v1/public/applications", "/api/v1/public/chapters"}` at `infra/tests/test_public_intake_channel_tripwire.py:27`). Keep backend `server-manager-api:8000` verbatim (validated at lines 230-231 of the tripwire). `pathType: Prefix` is required (tripwire line 186). |

**Dev target (NEW):**
`gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`.

**Channel-derived strings present in this file:**

- Host: `api.dev.humility.gg` (single occurrence, in the rule's
  `host:` field). No TLS block, so this is the only place the host
  appears in this manifest.

## H2 — pomerium-side rate-limit YAML

**Local source (read-only reference):**
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
(45 lines; verbatim contents above).

| Local span | Resource fragment | Dev disposition |
|---|---|---|
| Lines 1-8 | Ingress metadata: name `web-public-intake`, namespace `auth-system`, labels (`app.kubernetes.io/name: pomerium`, `platform.humility.gg/init: "120"`) | **Carry name + namespace verbatim** (tripwire `_validate_pomerium_rate_limit` requires `Ingress` named `web-public-intake` in `auth-system`, lines 242-244). Drop the `init` label provenance; `app.kubernetes.io/name` is not validated and may be carried. |
| Lines 9-13 | Annotations: Step CA issuer trio (lines 10-12) + `konghq.com/plugins: public-intake-rate-limit` (line 13) | **Drop the three Step CA annotation lines (10-12)** per §3 line 180. Keep `konghq.com/plugins: public-intake-rate-limit` (tripwire line 173). |
| Lines 14-19 | `spec.ingressClassName: kong` (line 15) + TLS block (lines 16-19) — host `web.local.humility.local`, secretName `web-local-ingress-tls` | **Drop the entire TLS block (lines 16-19)** per §3 line 180. |
| Lines 20-44 | Rules: host `web.local.humility.local` (line 21); paths `/api/public/applications` (line 24), `/api/public/chapters` (line 31), `/api/applications` (line 38); each backend `pomerium-proxy:80` (lines 27-30, 34-37, 41-44) | **Substitute host → `web.dev.humility.gg` (line 21)**. Keep paths verbatim (validated by `WEB_PUBLIC_PATHS = {"/api/public/applications", "/api/public/chapters", "/api/applications"}` at tripwire lines 28-32). Keep backend `pomerium-proxy:80` verbatim (validated at tripwire lines 253-254). |

**Dev target (NEW):**
`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`.

**Channel-derived strings present in this file:**

- Host: `web.dev.humility.gg` (single occurrence).

## H3 — pomerium routes block

**Local source (read-only reference):**
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
(170 lines, three `InfisicalSecret` documents). The public-intake
routes block lives **inside the first document only**, under
`spec.managedSecretReference.template.data.config.yaml` (a literal
`|`-block YAML string). The other two documents
(`pomerium-shared-secret` lines 107-138; `pomerium-signing-key`
lines 140-170) are runtime secret carriers and are anti-scope for
dev (no Infisical runtime contract).

Within the first document:

| Local span | Fragment | Dev disposition |
|---|---|---|
| Lines 1-9 | InfisicalSecret metadata: name `pomerium-config`, namespace `auth-system`, labels | Carry name + namespace verbatim. Drop `platform.humility.gg/init: "114"` provenance label. |
| Lines 10-22 | `spec.hostAPI`, `spec.authentication.universalAuth.credentialsRef`, `spec.authentication.universalAuth.secretsScope` (incl. `envSlug: local` line 18, `secretsPath: /auth/local/pomerium` line 19), `spec.syncConfig` | **Anti-scope for dev** — proposal §3 lines 192-196 forbids inventing a dev Infisical runtime contract. The dev manifest must NOT carry `hostAPI`, `authentication`, or `syncConfig` blocks. The minimum dev form is an outer `InfisicalSecret` skeleton whose only purpose is to host `spec.managedSecretReference.template.data.config.yaml` for the BL-013 parser. (See parser at tripwire lines 317-332: it reads only `spec.managedSecretReference.template.data["config.yaml"]` (or fallback `pomerium-config`), ignoring everything else on the doc.) |
| Lines 23-30 | `spec.managedSecretReference` envelope (secretName, secretNamespace, secretType, creationPolicy, template.includeAllSecrets) | **Carry shape verbatim** so the parser path `.spec.managedSecretReference.template.data["config.yaml"]` resolves. `creationPolicy: Owner`, `secretType: Opaque`, `includeAllSecrets: false` are not validated and may be dropped if simplicity is preferred — but the path keys themselves (`managedSecretReference.template.data.config.yaml`) MUST exist. |
| Line 32 | `authenticate_service_url: https://authenticate.local.humility.local` | **Substitute → `authenticate_service_url: https://authenticate.dev.humility.gg`** per Q2. |
| Line 33 | `idp_provider: oidc` | Carry verbatim (channel-invariant). |
| Line 34 | `idp_provider_url: https://auth.local.humility.local/application/o/pomerium/` | **Substitute → `idp_provider_url: https://auth.dev.humility.gg/application/o/pomerium/`** per Q2. |
| Lines 35-37 | `idp_client_id`, `idp_client_secret` (Infisical templates), `idp_scopes` | **Drop the two `{{ .OIDC_CLIENT_*.Value }}` template lines** — they imply the dev Infisical contract that is anti-scope. `idp_scopes` is not validated and may be dropped or carried. The tripwire does not require any of these three fields. |
| Lines 38-41 | `# LOCAL ONLY` comments + `insecure_server: true` (line 39) + `grpc_insecure: true` (line 41) | **Drop all four lines** per §3 line 192 ("No local-only `insecure_server` or `grpc_insecure` settings"). |
| Lines 42-47 | `jwt_claims_headers` block | Carry verbatim or drop; not validated by the tripwire. Recommend dropping for minimum slice surface. |
| Lines 48-100 | `routes:` list — nine entries on `https://web.local.humility.local` (eight identity-bearing + one public catch-all) | **Substitute every `from: https://web.local.humility.local` → `from: https://web.dev.humility.gg`**. Preserve the ordering: identity-bearing routes BEFORE the public catch-all (Q4 lines 109-119; tripwire `_validate_pomerium_routes` line 376 asserts every identity-route index < public-route index). The eight identity routes the proposal Q4 enumerates correspond to local lines:<br>– `/api/me` at line 49 (path)<br>– `/api/web/admin/` at line 55 (prefix)<br>– `/api/web/officer/` at line 61 (prefix)<br>– `/applications/queue` at line 67 (path)<br>– `/applications/queue/` at line 73 (prefix)<br>– `/applications/` at line 79 (prefix)<br>– `/admin` at line 85 (prefix)<br>– `/auth/discord/` at line 91 (prefix; public passthrough — note `allow_public_unauthenticated_access: true` at line 96, but `to:` is the API service `http://server-manager-api.server-manager.svc.cluster.local:8000`, not `WEB_UPSTREAM`, so the tripwire's public-catch-all detector does NOT bind to this route)<br>– public catch-all at lines 97-100 with `to: http://server-manager-web.web.svc.cluster.local:8080` (the tripwire's `WEB_UPSTREAM`). |
| Lines 101-105 | Protected-API route: `from: https://protected-api.local.humility.local`, `to: http://server-manager-api.server-manager.svc.cluster.local:8000`, identity-bearing (`allow_any_authenticated_user: true`) | **Substitute → `from: https://protected-api.dev.humility.gg`** per Q2. The `to:` upstream is a Kubernetes-internal Service URL and is channel-invariant. The tripwire does not match this route (it filters on `from == https://web.<channel>.humility.gg` at line 361), so this route is documentation-of-intent for the proposal §3 statement "protected API route using `https://protected-api.dev.humility.gg`" and for the TG-2 negative assertion that `protected-api.local.humility.local` is absent (proposal line 248). |
| Lines 106-170 | `---` doc separator + `pomerium-shared-secret` doc + `pomerium-signing-key` doc | **Drop both follow-on documents.** They are runtime secret carriers backed by Infisical templates (`{{ .SHARED_SECRET.Value }}`, `{{ .COOKIE_SECRET.Value }}`, `{{ .SIGNING_KEY.Value }}`) and embed `envSlug: local`, `secretsPath: /auth/local/pomerium`. They are not required by the BL-013 tripwire and they would imply a dev Infisical runtime contract that is anti-scope. The dev manifest contains exactly **one** `InfisicalSecret` document (the `pomerium-config` one). |

**Dev target (NEW):**
`gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`.

**Channel-derived strings present in this file:**

- `authenticate_service_url: https://authenticate.dev.humility.gg`
- `idp_provider_url: https://auth.dev.humility.gg/application/o/pomerium/`
- `from: https://web.dev.humility.gg` (8 identity routes + 1 public catch-all = 9 occurrences)
- `from: https://protected-api.dev.humility.gg` (1 occurrence)

**Channel-invariant strings preserved:**

- `to: http://server-manager-web.web.svc.cluster.local:8080` (8 identity web routes + 1 public catch-all = 9 occurrences)
- `to: http://server-manager-api.server-manager.svc.cluster.local:8000` (1 occurrence on `/auth/discord/`; 1 on protected-api = 2 occurrences)
- `allow_public_unauthenticated_access: true` (on `/auth/discord/` + the public catch-all)
- `allow_any_authenticated_user: true` (on the seven identity-bearing web routes + protected-api)

## H4 — Cedar policies file

**Existing dev file (modified, not new):**
`policy/cedar/channels/dev/services/server-manager-api/policies.json`
(currently 14 lines, 3 entries: `dev-server-manager-api-user-read`,
`dev-server-manager-api-buildkite-deploy`,
`dev-cluster-api-crossplane-reconcile`).

**Append two entries**, mirroring local lines 11-17 with the dev
public principal substitution. Local source for reference:

| Local span | Fragment | Dev disposition |
|---|---|---|
| `policy/cedar/channels/local/services/server-manager-api/policies.json` lines 10-13 | `{"id": "public-intake-allow", "content": "permit(principal == Public::\"web-intake.local\", action == Action::\"application:submit_public\", resource == Resource::\"server-manager-api:public-applications\");"}` | **Append to dev policies.json** with `Public::"web-intake.local"` → `Public::"web-intake.dev"`. Policy id `public-intake-allow` is canonical and MUST not be renamed (tripwire `_validate_cedar_policies` line 286 keys on this id). |
| `policy/cedar/channels/local/services/server-manager-api/policies.json` lines 14-17 | `{"id": "public-intake-no-read", "content": "forbid(principal == Public::\"web-intake.local\", action == Action::\"api:read\", resource == Resource::\"server-manager-api\");"}` | **Append to dev policies.json** with `Public::"web-intake.local"` → `Public::"web-intake.dev"`. Policy id `public-intake-no-read` is canonical (tripwire line 293). |

The two appended entries must use the exact substring set the
tripwire's `_validate_cedar_policies` checks (lines 284-298):

For `public-intake-allow`:
- `permit(`
- `Public::"web-intake.dev"`
- `Action::"application:submit_public"`
- `Resource::"server-manager-api:public-applications"`

For `public-intake-no-read`:
- `forbid(`
- `Public::"web-intake.dev"`
- `Action::"api:read"`
- `Resource::"server-manager-api"`

**Local-only entries that MUST NOT be carried into dev:**

- `local-server-manager-api-user-read` (`User::"sample@local.humility.local"`)
- `local-server-manager-api-buildkite-deploy` (`Service::"buildkite-agent.local"`)
- `local-cluster-api-crossplane-reconcile` (`Service::"crossplane-provider.local"`)
- `local-tenant-sample-local-access` (`Tenant::"sample"` → `TenantChannel::"sample:local"`)
- `local-tenant-sample-dev-access` (lives in the local file as a cross-channel grant; do NOT migrate)
- `local-tenant-other-local-access` (`Tenant::"other"` → `TenantChannel::"other:local"`)

The existing dev entries (`dev-server-manager-api-user-read`,
`dev-server-manager-api-buildkite-deploy`,
`dev-cluster-api-crossplane-reconcile`) MUST be preserved
verbatim (proposal §3 line 204; audit §1 lines 124-126).

`policy/cedar/channels/dev/services/server-manager-api/manifest.yaml`
and `service-identities.json` are NOT touched (Q3 lines 99-100 forbid
adding a service-identity entry for the public principal).

**Channel-derived strings appended:** `Public::"web-intake.dev"`
(2 occurrences, one per policy).

## H5 — kustomization.yaml for discoverability

**Dev target (NEW):** `gitops/channels/dev/kustomization.yaml`.

Per Q5 (proposal lines 137-153) the kustomization references the
three new dev manifest files directly with NO intermediate
kustomizations:

```yaml
resources:
  - applications/server-manager/public-intake-rate-limit.yaml
  - auth/pomerium/public-intake-rate-limit.yaml
  - auth/pomerium/secrets-infisicalsecret.yaml
```

The minimum legal `kustomize build` shape adds an
`apiVersion: kustomize.config.k8s.io/v1beta1` + `kind: Kustomization`
header to that resources list. There is no local equivalent to copy
from at the channel-root level (the local channel has no top-level
`gitops/channels/local/kustomization.yaml`); H5 has no local source
hookpoint and is greenfield.

**Anti-hookpoints under H5** (must NOT be created in this slice per
Q5 lines 150-153):

- `gitops/channels/dev/applications/kustomization.yaml`
- `gitops/channels/dev/applications/server-manager/kustomization.yaml`
- `gitops/channels/dev/auth/kustomization.yaml`
- `gitops/channels/dev/auth/pomerium/kustomization.yaml`

TG-4 (proposal lines 270-282) asserts:
- `kustomize build gitops/channels/dev/` exits 0
- output includes the API-side `KongPlugin` and `Ingress`
- output includes `Ingress/web-public-intake`
- output includes the Pomerium config-bearing manifest

A `kustomization.yaml` with `resources: []` would pass exit 0 but
fail the content-presence assertions (shortcut gate C4 lines 290-294).

**Channel-derived strings present:** none. Resource paths are
relative to the kustomization root and are channel-invariant
(every channel that materializes the same three substrate files
ends up with the identical kustomization content).

## H6 — test extension points

**Existing test source (read-only by default):**
`infra/tests/test_public_intake_channel_tripwire.py` (612 lines).

Proposal §3 lines 207-214 + §6 lines 337-342: "Prefer zero
test-file changes. … No change should be required. … Only extend
this test if implementation reveals that discovery or validation is
not channel-derived enough for the real dev files. Do not weaken
the tripwire to accommodate partial materialization."

The tripwire is **already channel-derived**. The dev substrate
must satisfy these binding hookpoints in the existing test source
(no edits expected):

| Tripwire hookpoint | Line range | What it pins |
|---|---|---|
| Constants | 14-33 | `PLUGIN_NAME = "public-intake-rate-limit"`, `API_PUBLIC_PATHS`, `WEB_PUBLIC_PATHS`, `PUBLIC_TRIGGER_NAMES`, `WEB_UPSTREAM = "http://server-manager-web.web.svc.cluster.local:8080"` |
| `_is_public_intake_relevant` | 94-114 | Discovery trigger: any `*.y*ml` under `gitops/channels/<channel>/applications/server-manager/` whose filename is `public-intake-rate-limit.yaml`, or whose metadata.name ∈ `PUBLIC_TRIGGER_NAMES`, or whose Ingress paths intersect `PUBLIC_TRIGGER_PATHS`. The dev API manifest matches all three signals (filename, KongPlugin/Ingress names, paths). |
| `discover_channels` skip-local | 124-125 | `if channel_dir.name == "local": continue`. Local cannot regress and dev becomes the first non-local discovered channel. |
| `_validate_api_rate_limit` | 202-233 | Reads `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`; requires `KongPlugin` named `public-intake-rate-limit` in `server-manager`, Ingress `server-manager-public-intake-api`, host `api.dev.humility.gg` (line 228 substitutes `{channel}`), paths `API_PUBLIC_PATHS`, backend `server-manager-api:8000`, `pathType: Prefix`, plugin annotation. |
| `_validate_pomerium_rate_limit` | 236-256 | Reads `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`; Ingress `web-public-intake` in `auth-system`, host `web.dev.humility.gg` (line 251), paths `WEB_PUBLIC_PATHS`, backend `pomerium-proxy:80`. |
| `_validate_cedar_policies` | 269-314 | Reads `policy/cedar/channels/dev/services/server-manager-api/policies.json`; requires policy ids `public-intake-allow` (permit + `Public::"web-intake.dev"` + canonical action/resource) and `public-intake-no-read` (forbid). The check at line 305-308 explicitly fails any non-local channel whose policy contains `Public::"web-intake.local"`. |
| `_pomerium_config_documents` parser | 317-332 | Walks `spec.managedSecretReference.template.data["config.yaml"]` (or `pomerium-config` fallback) and `yaml.safe_load_all`s the embedded string. Determines the structural shape H3 must preserve. |
| `_validate_pomerium_routes` | 335-384 | Reads `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`; requires at least one route with `from: https://web.dev.humility.gg`, `allow_public_unauthenticated_access: true`, `to: WEB_UPSTREAM`; requires at least one identity-bearing route on the same `from` host; requires identity-route indexes < public-catch-all index (line 376). |
| `test_repository_state_passes` | 569-574 | The single CI-binding test that calls `discover_channels(GITOPS_ROOT)` + `verify_substrate(channel, GITOPS_ROOT, CEDAR_ROOT)`. After the dev substrate lands this is the green/red signal. |

**Conditional extension contract (only if implementation reveals a
gap)** — proposal §3 lines 211-214. A bounded extension is
authorized **only** to add channel-derived assertions that the dev
substrate exposes as missing; it is NOT authorized to weaken any
existing assertion to accommodate partial materialization.

Allowed extension shapes:

1. Add a static literal-substring assertion that the dev Cedar
   policies file does NOT contain `Public::"web-intake.local"` (TG-3
   line 263). The current `_validate_cedar_policies` already covers
   this via the `local_principal` check at line 305-308; an
   additional file-scoped substring sweep would be belt-and-braces
   and is the only realistic test edit envisioned.
2. Add a regex sweep at `gitops/channels/dev/` + the dev Cedar
   policy file for the TG-5 banned strings (proposal lines 287-296):
   `*.local.humility.local`, `web-intake.local`, `/auth/local/`,
   `/postgres/local/`, `/object-storage/local/`, `/runtime/local`,
   local Step CA issuer annotations, local ingress TLS secret names,
   `policy/cedar/channels/local`. The sweep MUST exempt
   `.svc.cluster.local` (TG-5 line 297-298). This sweep does not
   exist in the current test source; if added, it must be scoped to
   `gitops/channels/dev/` (not local, not all channels) and must not
   regress the existing `verify_substrate` checks.
3. Add a TG-2 standalone parser test that asserts the embedded
   Pomerium `config.yaml` is valid YAML with a `routes` list and
   that no route source contains `web.local.humility.local` or
   `protected-api.local.humility.local` (proposal lines 244-249). The
   existing `_validate_pomerium_routes` already enforces ordering on
   the dev `from:` host but does not negative-assert local hosts; a
   dedicated negative assertion is in scope as a focused extension.
4. Add a TG-4 invocation that runs `kustomize build gitops/channels/dev/`
   via subprocess and asserts the three manifests appear in stdout.
   The existing test source has no kustomize-build coverage; this is
   a permissible extension if `kustomize` is available in CI.

**Forbidden extension shapes** (would weaken or expand scope):

- Removing or relaxing `discover_channels`'s `local` skip.
- Adding a `local`-channel assertion (local is the reference, not
  in the tripwire's validation set).
- Adding a `dev`-only conditional that bypasses any
  `verify_substrate` validator.
- Materializing a dev Infisical runtime contract assertion.
- Renaming canonical policy ids `public-intake-allow` /
  `public-intake-no-read`.
- Adding a Vultr/Flux/DNS/cert assertion.

**Channel-derived strings used at test-time:** every assertion that
references the channel folds through the `{channel}` parameter at
lines 228, 251, 281, 357. No literal `dev` string is hardcoded in
the test source; the dev substrate is validated entirely via the
folder name → format-string substitution.

HOOKPOINTS_DONE: research/49-init-138-hookpoints.md
