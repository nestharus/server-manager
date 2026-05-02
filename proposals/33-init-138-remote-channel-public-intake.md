# Proposal 33 - INIT-138: Remote channel public-intake substrate

## 1. Problem statement

`gitops/channels/local/` is the only materialized application GitOps channel
today. It contains the public-intake substrate as a local-only snapshot:

- API-side rate limiting and public API ingress at
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`.
- Pomerium/web-side public ingress at
  `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`.
- Pomerium route coverage in
  `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`.
- Cedar public submit allow and public read forbid policies in
  `policy/cedar/channels/local/services/server-manager-api/policies.json`.

`policy/cedar/channels/dev/` already exists, but `gitops/channels/dev/` does
not. The dev channel contract in `infra/channels/dev.yaml` resolves as a remote
`vultr-vms` channel with `ingress.remote_domain: humility.gg`, dev access
policy paths, dev service principals, and no `gitops`, `auth_stack`,
`infisical`, `observability`, `security`, or `tenant_isolation` runtime blocks.

BL-013 now has a static tripwire in
`infra/tests/test_public_intake_channel_tripwire.py`. It intentionally ignores
absent non-local channel directories, but once a non-local channel contains
public-intake-relevant `applications/server-manager` material, it requires the
matching channel-local API ingress, Pomerium ingress, Cedar policies, and
Pomerium route block. INIT-138 is the narrow manifest-authoring slice that makes
that tripwire actionable for `dev`.

The scope is the problem-map Option A: materialize only the `dev`
public-intake substrate required by BL-013, using channel-derived hosts and
principals. This is not a full remote runtime, a full channel template, or a
Vultr apply.

## 2. Decisions

### Q1. Scope option

Lock Option A: narrow public-intake-only port for `dev`.

The implementation must create the smallest `gitops/channels/dev/` substrate
that lets static CI validate the same logical public-intake surface already
present in `local`. Do not copy the whole local channel and do not introduce a
template/refactor system in this slice.

The `dev` substrate is partial by design. It may be valid for static manifest
checks and future runtime work, but it must not be described as a runnable
remote server-manager deployment.

### Q2. Channel-derived values

Lock these derived values for `dev`:

```text
API hostname:      api.dev.humility.gg
Web hostname:      web.dev.humility.gg
Protected API:     protected-api.dev.humility.gg
Authenticate URL:  https://authenticate.dev.humility.gg
IdP provider URL:  https://auth.dev.humility.gg/application/o/pomerium/
Public principal:  Public::"web-intake.dev"
```

The hostname domain comes from `infra/channels/dev.yaml`:
`ingress.remote_domain: humility.gg`. The auth host convention is already used
by the dev access-policy issuer:
`https://auth.dev.humility.gg/application/o/humility-service-identities/`.

Do not use `*.local.humility.local`, `web-intake.local`,
`Service::"*.local"`, `/auth/local/...`, local Step CA issuers, local ingress
TLS secret names, or local DNS aliases in the new dev public-intake manifests.
Internal Kubernetes service DNS such as
`server-manager-web.web.svc.cluster.local` is not a channel hard-code and
remains allowed where Pomerium needs an in-cluster upstream.

### Q3. Cedar policies

Extend
`policy/cedar/channels/dev/services/server-manager-api/policies.json` with the
same public-intake allow/forbid pair used by local, but with the dev public
principal:

```cedar
permit(
  principal == Public::"web-intake.dev",
  action == Action::"application:submit_public",
  resource == Resource::"server-manager-api:public-applications"
);

forbid(
  principal == Public::"web-intake.dev",
  action == Action::"api:read",
  resource == Resource::"server-manager-api"
);
```

Use the existing policy IDs `public-intake-allow` and
`public-intake-no-read`, because the BL-013 tripwire keys on those canonical
IDs. Do not add a service identity entry for public intake; the principal is a
public/anonymous Cedar principal, not an authenticated service account.

### Q4. Pomerium route coverage

Materialize the dev Pomerium public-intake route block in
`gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`.

The route block must preserve the local ordering rule:
identity-bearing `https://web.dev.humility.gg` routes come before the public
catch-all for the same host. The minimum web-host routes are:

- `/api/me`;
- `/api/web/admin/`;
- `/api/web/officer/`;
- `/applications/queue` and `/applications/queue/`;
- `/applications/`;
- `/admin`;
- `/auth/discord/` as public passthrough to the API;
- the public catch-all to
  `http://server-manager-web.web.svc.cluster.local:8080`.

The public ingress in
`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml` must expose
the same path set as local, but on `web.dev.humility.gg`:

- `/api/public/applications`;
- `/api/public/chapters`;
- `/api/applications`.

The API-side ingress in
`gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
must expose the same API public paths as local, but on
`api.dev.humility.gg`:

- `/api/v1/public/applications`;
- `/api/v1/public/chapters`.

### Q5. Kustomization wiring

Add a top-level `gitops/channels/dev/kustomization.yaml`.

It should reference only the three dev public-intake manifest files directly:

```yaml
resources:
  - applications/server-manager/public-intake-rate-limit.yaml
  - auth/pomerium/public-intake-rate-limit.yaml
  - auth/pomerium/secrets-infisicalsecret.yaml
```

Do not add intermediate `applications/`, `applications/server-manager/`,
`auth/`, or `auth/pomerium/` kustomizations in this slice. Direct references
keep the diff small and make `kustomize build gitops/channels/dev/` meaningful
without implying that the rest of the dev channel exists.

## 3. Substrate

### New files

- `gitops/channels/dev/kustomization.yaml`
  - Static build entrypoint for the narrow public-intake substrate only.

- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
  - `KongPlugin/public-intake-rate-limit` in namespace `server-manager`.
  - `Ingress/server-manager-public-intake-api` in namespace `server-manager`.
  - Host `api.dev.humility.gg`.
  - Prefix paths `/api/v1/public/applications` and
    `/api/v1/public/chapters`.
  - Backend `server-manager-api:8000`.
  - No local Step CA annotations or local TLS secret names.
  - Do not carry `config.policy: local` from the local KongPlugin; omit the
    policy field for this static slice unless a later runtime proposal chooses
    a remote rate-limit backend.

- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`
  - `Ingress/web-public-intake` in namespace `auth-system`.
  - Host `web.dev.humility.gg`.
  - Prefix paths `/api/public/applications`, `/api/public/chapters`, and
    `/api/applications`.
  - Backend `pomerium-proxy:80`.
  - No local Step CA annotations or local TLS secret names.

- `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`
  - Pomerium config-bearing manifest with `config.yaml` under
    `managedSecretReference.template.data`, so the BL-013 parser can validate
    the route block.
  - Dev route sources:
    `https://web.dev.humility.gg` and
    `https://protected-api.dev.humility.gg`.
  - Dev Pomerium URLs:
    `authenticate_service_url: https://authenticate.dev.humility.gg` and
    `idp_provider_url: https://auth.dev.humility.gg/application/o/pomerium/`.
  - No local-only `insecure_server` or `grpc_insecure` settings.
  - No invented dev Infisical runtime contract. If the manifest keeps the
    `InfisicalSecret` kind, it must be explicit that only the route template is
    in scope for static validation; runtime secret sourcing remains
    anti-scope until a dev `auth_stack`/Infisical contract exists.

### Modified files

- `policy/cedar/channels/dev/services/server-manager-api/policies.json`
  - Append `public-intake-allow`.
  - Append `public-intake-no-read`.
  - Preserve existing dev user, Buildkite, and Crossplane policies.

### Test changes

No change should be required to
`infra/tests/test_public_intake_channel_tripwire.py`. It already discovers
non-local channels through `gitops/channels/<channel>/applications/server-manager`
and validates channel-derived hosts and `Public::"web-intake.<channel>"`.

Only extend this test if implementation reveals that discovery or validation is
not channel-derived enough for the real dev files. Do not weaken the tripwire
to accommodate partial materialization.

## 4. Test plan

### TG-1: BL-013 tripwire discovers and validates dev

Run:

```bash
pytest infra/tests/test_public_intake_channel_tripwire.py
```

Acceptance:

- `discover_channels()` returns `dev` after the new API-side manifest exists;
- `verify_substrate("dev")` returns no failures;
- the API ingress uses `api.dev.humility.gg`;
- the Pomerium/web ingress uses `web.dev.humility.gg`;
- Cedar policies use `Public::"web-intake.dev"`;
- Pomerium route ordering keeps identity-bearing web routes before the public
  catch-all.

### TG-2: dev Pomerium route block parses

Parse the new Pomerium manifest with `yaml.safe_load_all`, then parse embedded
`managedSecretReference.template.data.config.yaml` with `yaml.safe_load`.

Acceptance:

- the outer manifest is valid YAML;
- the embedded Pomerium config is valid YAML;
- the embedded config has a `routes` list;
- the web public catch-all route points to
  `http://server-manager-web.web.svc.cluster.local:8080`;
- no route source contains `web.local.humility.local` or
  `protected-api.local.humility.local`.

### TG-3: dev Cedar policy file is valid and channel-derived

Run the existing policy JSON load path and a focused static check for the two
new policy objects.

Acceptance:

- `policy/cedar/channels/dev/services/server-manager-api/policies.json` is
  valid JSON;
- policy contents include syntactically complete Cedar statements for
  `public-intake-allow` and `public-intake-no-read`;
- both policies use `Public::"web-intake.dev"`;
- neither policy contains `Public::"web-intake.local"`.

If a local Cedar parser or policy materializer is available in the implementation
environment, run it against the two new statements. If not, the static literal
checks above are the required CI guard for this manifest-authoring slice.

### TG-4: dev kustomization builds

Run:

```bash
kustomize build gitops/channels/dev/
```

Acceptance:

- build exits successfully;
- output includes the API-side `KongPlugin` and `Ingress`;
- output includes `Ingress/web-public-intake`;
- output includes the Pomerium config-bearing manifest.

### TG-5: no channel-local hardcodes leak into dev manifests

Run a regex sweep over `gitops/channels/dev/` and the dev Cedar policy file.

Acceptance:

- no `*.local.humility.local` hosts;
- no `web-intake.local`;
- no `/auth/local/`, `/postgres/local/`, `/object-storage/local/`, or
  `/runtime/local` paths;
- no local Step CA issuer annotations or local ingress TLS secret names;
- no `policy/cedar/channels/local` references.

The sweep must not reject Kubernetes' internal DNS suffix
`.svc.cluster.local`; that string is not the Humility channel id.

## 5. Anti-scope

Do not apply anything to Vultr, Flux, Kubernetes, DNS, or certificate issuers.
This proposal is manifest authoring and static validation only.

Do not add dev Flux wiring, a dev `gitops` contract block, remote Git source
rendering, SOPS bootstrap, Cloudflare records, ACME issuer materialization, or
load balancer verification.

Do not port other subsystems: Authentik, MinIO/object-storage runtime, Postgres
CNPG, Atlas, OPAL, Pomerium proxy deployment, server-manager API/web
deployments, Buildkite, app-clusters, tenant isolation, observability, or
security policies beyond the public-intake route block and Cedar policy pair.

Do not introduce a channel templating refactor, Kustomize base/overlay system,
renderer changes, compatibility shims, feature flags, deprecated aliases,
dual-host support, or fallback principals.

Do not modify any local channel manifest. The local channel remains the
reference implementation for this narrow port.

## 6. Diff budget

Expected GitOps diff:

- Add `gitops/channels/dev/kustomization.yaml`.
- Add
  `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`.
- Add `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`.
- Add `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml`.

Expected policy diff:

- Update
  `policy/cedar/channels/dev/services/server-manager-api/policies.json` with
  two policy objects.

Expected test diff:

- Prefer zero test-file changes.
- At most, add focused assertions to
  `infra/tests/test_public_intake_channel_tripwire.py` if the real dev
  substrate exposes a missing channel-derived check.

No production API, Discord daemon, web app, migration, generated client,
runtime script, local manifest, or deployment code changes are budgeted.

PROPOSAL_DONE: proposals/33-init-138-remote-channel-public-intake.md
