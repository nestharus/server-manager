# INIT-138 problem map -- remote channel application-workload materialization

## What "channel-template port" means

In this repository, a "channel-template port" can mean two different scopes:

- Narrow BL-013 unblock: materialize the server-manager public-intake workload substrate for a non-local channel, with channel-derived hosts and policy principals, plus static validation. This is not a full remote runtime.
- Full channel template: turn the current `gitops/channels/local/` snapshot into a reusable channel manifest source for every subsystem, so `gitops/channels/dev/` can be generated as a complete platform channel.

The current local channel is a checked-in materialized snapshot, not a template. It contains 232 files, 230 YAML files, and these top-level subsystems:

| Subsystem | YAML count | Portability classification | Channel-template notes |
|---|---:|---|---|
| `access-policy` | 7 | Portable with channel parameters | Service identity issuer, Cedar principals, policy paths, and operator group/claim namespace are channel contract values. |
| `app-clusters` | 29 | Mixed: portable API, local singleton runtime pieces | XRD and Vultr composition are reusable; `appcluster-k3d-local`, local sample claim, Flux paths, source names, and Docker socket runtime are local-specific. |
| `applications` | 27 | Portable workload surface with channel parameters | This is the BL-013 narrow target. Server-manager and web manifests need image refs, hosts, secret paths, object storage, backup destinations, and channel labels parameterized. |
| `auth` | 21 | Mixed: portable route intent, local-specific rendered runtime | Authentik/Pomerium/OPAL logical config is portable, but local Step CA, all-in-one Pomerium patch, local hosts, local sample user, and local Infisical paths are embedded. |
| `cicd` | 8 | Portable with channel parameters | Buildkite queue, token path, and agent identity are channel-derived; local mode messaging is local-specific. |
| `data-plane` | 16 | Portable with storage/runtime parameters | CNPG/Atlas operator manifests are mostly shared, but sample DB size, backup endpoint, bucket paths, and Infisical paths vary by channel. |
| `dns` | 3 | Local singleton | Current manifests are CoreDNS aliases for `humility.local`; remote dev uses Cloudflare/external-dns contracts instead. |
| `generated` | 1 | Generated singleton | `gitops-snapshot-marker.yaml` is renderer output and should not be hand-templated as source. |
| `image-registry` | 3 | Portable with provider split | Local k3d registry and pull-through cache differ from dev Vultr Container Registry. |
| `infisical` | 12 | Local bootstrap singleton for local, remote dependency for dev | Local deploys Infisical server/operator/sample. Dev does not currently define `infisical` in `infra/channels/dev.yaml`; remote manifests assume an operator/auth substrate but not a dev Infisical server block. |
| `ingress` | 12 | Mixed | Kong is portable, but local `ClusterIP`, local DNS alias/default MinIO ingress, Step CA issuer annotations, and `*.local.humility.local` hosts are local-only. Remote dev expects `LoadBalancer` plus remote DNS/TLS. |
| `object-storage` | 13 | Local singleton for MinIO; remote provider contracts differ | Local deploys MinIO and bucket jobs. Dev uses Vultr Object Storage, so a full port must replace these with remote secret/policy manifests rather than copy MinIO. |
| `observability` | 35 | Mostly portable, but dev contract is incomplete | Workloads can be parameterized, but local buckets, secret paths, labels, alert receiver names, and MinIO endpoints are embedded. `dev.yaml` has no `observability` block today. |
| `security` | 7 | Mixed | Baseline policies are portable, but local namespace lists and local-only exceptions are embedded. |
| `tenants` | 16 | Portable sample model with channel parameters | Tenant namespace pattern is defined in `local.yaml`, but checked-in sample manifests hard-code `sample-local`, `sample-dev`, `other-local`, labels, and Infisical env/path values. |
| `tls` | 18 | Local singleton for Step CA; remote provider contracts differ | Local deploys cert-manager, Step CA, Step issuer, and sample certificate. Dev uses ACME/Cloudflare fields and existing remote `gitops/contracts/remote/tls-dns/`. |

The BL-013 source framing says: "Block on remote channel application-workload materialization (separate initiative). Then this is a channel-template port: same logical resources, channel-derived hosts." That points at the narrow meaning for INIT-138: port the application workload substrate needed by public intake, not the whole local channel platform.

## Channel-parameterized variables

The local tree embeds channel-specific values in several categories:

- Channel id and labels: `platform.humility.gg/channel: local`, tenant-channel names like `sample-local`, policy `channel: local`, bundle ids like `local.server-manager-api`.
- Hosts and domains: `api.local.humility.local`, `web.local.humility.local`, `auth.local.humility.local`, `authenticate.local.humility.local`, `protected-api.local.humility.local`, `minio.local.humility.local`, and local service aliases under `humility.local`. Dev channel config instead points at remote patterns such as `auth.dev.humility.gg`, `minio.dev.humility.gg`, and BL-013 expects `api.dev.humility.gg` / `web.dev.humility.gg`.
- TLS issuers and secret names: `humility-local-step-ca`, `*-local-ingress-tls`, `cert-manager.io/issuer-kind: StepClusterIssuer`, and Step CA trust mounts are local. Dev uses `letsencrypt-staging` and Cloudflare DNS fields.
- Image references: local workloads use `k3d-humility-local:5000/local/...:init-*-local`; dev channel config has `ewr.vultrcr.com/humility` and repository prefix `dev`.
- Secret sync locations: many `InfisicalSecret` manifests use `hostAPI: http://infisical.infisical-system.svc.cluster.local:8080`, `envSlug: local`, and paths such as `/runtime/local`, `/postgres/local/server-manager`, `/auth/local/pomerium`, `/auth/local/authentik`, `/object-storage/local`, and `/buildkite/local`. Dev has `/buildkite/dev`, `/object-storage/dev`, `/postgres/dev/sample-app`, `/registry/dev`, and no `auth_stack`/server-manager runtime paths yet.
- Object storage endpoints and buckets: local uses MinIO service URLs, `us-east-1`, `humility-local-sample`, `humility-local-backups`, `humility-local-observability`, and `s3://.../cnpg/local/...`. Dev uses Vultr Object Storage, region `ewr`, and buckets such as `humility-dev-sample` and `humility-dev-backups`.
- Database settings: CNPG clusters are portable, but storage sizes, backup destinations, app secret names, and database credential paths are channel-specific. Server-manager database config exists only in local manifests; dev channel config currently has sample data-plane fields, not server-manager app database fields.
- Auth and policy principals: local has `sample@local.humility.local`, `Public::"web-intake.local"`, `Service::"buildkite-agent.local"`, and `Service::"crossplane-provider.local"`. Dev policy files already use `sample@dev.humility.gg`, `Service::"buildkite-agent.dev"`, and `Service::"crossplane-provider.dev"`, but do not yet include the BL-013 public-intake allow/forbid policies.
- Pomerium route config: local route sources all use `https://web.local.humility.local` and `https://protected-api.local.humility.local`, plus local-only `insecure_server` / `grpc_insecure` all-in-one settings. A dev port needs remote hosts and must preserve protected-route ordering before the public catch-all.
- Kong ingress exposure: local Kong is `ClusterIP`; dev channel config says `LoadBalancer`. Public-intake `KongPlugin` config currently uses `policy: local`, which may still be acceptable for static validation but is a runtime choice for remote deployment.
- Flux/GitOps fields: local has `gitops.path: ./gitops/channels/local`, `kustomization_name: humility-local`, source URL `http://git-local.../humility-local.git`, and app-cluster Flux kustomizations with hard-coded `./gitops/channels/local/...` paths. `dev.yaml` deliberately omits `gitops`.
- Bootstrap/local-only infrastructure: local Git server, CoreDNS alias service, Step CA, MinIO, k3d app-cluster composition, Docker socket provider runtime, and local sample bootstrap users are not directly portable to a remote channel.

## Existing templating substrate

There is no `gitops/channels/_template/`, no `gitops/channels/base`, and no Kustomize overlay hierarchy under `gitops/channels/`. The only materialized channel directory is `gitops/channels/local/`.

The channel contract exists in `infra/channels/*.yaml` plus the JSON schemas and resolver:

- `infra/channels/local.yaml` is a complete local contract. It includes `gitops`, `infisical`, `object_storage`, `image_registry`, `cicd`, `ingress`, `auth_stack`, `access_policy`, `data_plane`, `backup`, `tls`, `dns`, `app_cluster`, `security`, `tenant_isolation`, and `observability`.
- `infra/channels/dev.yaml` exists and resolves successfully, but it deliberately omits `gitops`. It also omits `infisical`, `auth_stack`, `observability`, `security`, and `tenant_isolation`.
- The resolver does deep parent merging and schema validation. It does not derive hostnames, image refs, or GitOps paths beyond a small object-storage endpoint default for Vultr regions.
- The schemas already distinguish local-only requirements from remote fields. For `k3d-local`, local `gitops`, MinIO, Step CA, CoreDNS, local app-cluster, security, and tenant-isolation fields are required. For `vultr-vms`, dev-style remote fields are allowed without `gitops`.

`infra/scripts/render-gitops-source.py` is a snapshot renderer, not a channel manifest template renderer:

- It requires a resolved `gitops` block, so it cannot render `dev` today.
- It copies the entire `gitops/` tree and the entire `policy/` tree into the output snapshot.
- It derives Flux `GitRepository` and `Kustomization` from `resolved.gitops`.
- It substitutes only two tokens in local server-manager files: `__ALEMBIC_HASH__` and `__SEED_HASH__`.
- It hard-codes Cedar local paths:
  - `policy/cedar/channels/local/services/server-manager-api/policies.json`
  - `policy/cedar/channels/local/services/server-manager-api/generated/policies`
- It writes a generated marker into the resolved GitOps source path.

There are remote contract fragments under `gitops/contracts/remote/` for app-clusters, image-registry, and tls-dns. These are useful precedents for provider-specific remote manifests, but they are not wired as a per-channel template system and they do not cover `applications/server-manager`, `applications/web`, Pomerium, Cedar public-intake policy, or server-manager runtime/database secrets.

BL-013's current static tripwire exists in `infra/tests/test_public_intake_channel_tripwire.py`. It validates non-local channels only after public-intake-relevant server-manager manifests appear, and then expects the API rate-limit ingress, Pomerium/web rate-limit ingress, Cedar public-intake policies, and Pomerium public route coverage. INIT-138 is the manifest materialization work that makes that tripwire actionable for `dev`.

## Scope options

### Option A: narrow public-intake-only port for dev

This option creates the smallest remote channel manifest substrate that unblocks BL-013 without claiming a full dev runtime.

Minimum public-intake substrate for `dev`:

- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml` with:
  - `KongPlugin/public-intake-rate-limit` in namespace `server-manager`
  - `Ingress/server-manager-public-intake-api`
  - host `api.dev.humility.gg`
  - paths `/api/v1/public/applications` and `/api/v1/public/chapters`
  - backend `server-manager-api:8000`
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml` with:
  - `Ingress/web-public-intake` in namespace `auth-system`
  - host `web.dev.humility.gg`
  - paths `/api/public/applications`, `/api/public/chapters`, and `/api/applications`
  - backend `pomerium-proxy:80`
- `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml` or a static equivalent sufficient for validation with:
  - route sources using `https://web.dev.humility.gg`
  - identity-bearing web routes before the public catch-all
  - public catch-all to `http://server-manager-web.web.svc.cluster.local:8080`
  - protected API route using `https://protected-api.dev.humility.gg` if protected API is included in the route config
- `policy/cedar/channels/dev/services/server-manager-api/policies.json` updated with:
  - `public-intake-allow` for `Public::"web-intake.dev"` and `Action::"application:submit_public"`
  - `public-intake-no-read` forbidding `Action::"api:read"` for the same public principal
- Static validation that `dev` does not retain local hosts, local public principals, or local-only public-intake paths.

This option should not copy the whole server-manager app directory unless the proposal accepts the extra config surface. The narrowest version can be a public-intake substrate slice with only the files the BL-013 tripwire requires. That is enough for manifest authoring and static validation, but it does not produce a runnable remote application.

### Option B: full template port

This option turns `gitops/channels/local/` into a complete multi-channel source and ships a full `gitops/channels/dev/`.

It includes all of Option A plus:

- A channel template source for all top-level subsystems listed above.
- Remote equivalents for local-only platform pieces:
  - MinIO local object storage replaced by Vultr Object Storage secret/policy manifests.
  - Step CA/CoreDNS local DNS/TLS replaced by ACME and external-dns.
  - k3d registry replaced by Vultr Container Registry.
  - k3d app-cluster composition/sample claim either omitted for dev or replaced by `vultr-vms` claim material.
  - local Git server/Flux path decisions resolved for dev by adding a `gitops` block or a different render source.
- Server-manager runtime support for dev:
  - image references from `dev.image_registry`
  - server-manager database credentials/URL paths
  - object storage bucket and backup credentials
  - Authentik/Pomerium runtime secret paths
  - OIDC redirect URLs and issuer URLs for dev
- Full policy channel generation:
  - Cedar bundle paths for `policy/cedar/channels/<channel>`
  - service identities
  - tenant policy samples if tenants ship in dev
- Full static validation:
  - no local hostnames in `gitops/channels/dev`
  - no local image registry refs
  - no local Step CA issuer annotations unless explicitly local
  - no MinIO-only manifests in remote provider channels
  - all Kustomize references resolve
  - rendered source does not hard-code `policy/cedar/channels/local`

This is the clean long-term shape, but it is many slices: channel contract expansion, renderer changes, generated-manifest strategy, remote provider substitution, server-manager runtime contract, auth runtime contract, and validation.

### Option C: introduce a Kustomize base + per-channel overlay refactor

This option creates a shared base and channel overlays instead of direct copying or a custom renderer-only template system.

Likely shape:

- Shared bases for portable resources:
  - `applications/server-manager`
  - `applications/web`
  - Pomerium route intent
  - Kong public-intake ingresses
  - CNPG/Atlas app database resources
  - common network policies
- Overlays for `local` and `dev`:
  - local overlay applies Step CA issuer, local hosts, k3d image refs, MinIO endpoints, local Infisical paths, local DNS aliases
  - dev overlay applies ACME issuer, remote hosts, Vultr registry refs, Vultr object storage, remote DNS/TLS resources
- Kustomize replacements or generated channel parameter ConfigMaps for hostnames, image refs, channel labels, and owner ids.

This uses established Kubernetes tooling and can reduce custom string templating, but it is still a broad refactor. It also risks pulling local's currently stable manifests through a new composition system before the remote application-workload slice has proven its exact needs.

## Recommendation

Land Option A first, with a narrow definition: materialize only the remote public-intake application substrate required by BL-013 for `dev`, using channel-derived values and static validation. Do not claim full remote runtime readiness and do not port local-only platform subsystems.

The reason is scope control. BL-013 needs the same logical public-intake resources with channel-derived hosts. It does not need MinIO-to-Vultr object storage migration, remote Flux wiring, Step CA replacement, Authentik remote deployment strategy, observability, tenant samples, or app-cluster provisioning. Those are real full-port concerns, but mixing them into INIT-138 would make the BL-013 unblock depend on unrelated platform decisions.

The recommended contract for INIT-138 should say:

- `dev` public-intake manifests are authored statically under `gitops/channels/dev/...`.
- They are valid for static CI checks and future remote apply, but this initiative does not require a Vultr runtime.
- The only required server-manager application material is the public-intake substrate group identified by BL-013.
- Cedar dev public-intake policy is updated in the existing `policy/cedar/channels/dev/services/server-manager-api/policies.json`.
- Existing local manifests stay as the reference implementation; no broad local refactor is part of this slice.
- Full channel templating remains a follow-up initiative once remote runtime choices are ready.

Option C is a good later design direction if multiple remote channels begin to repeat the same files. It should not be the first INIT-138 implementation unless the proposal intentionally expands the task into a template-system refactor.

## Diff budget per option

| Option | Expected artifact/code footprint | Static validation footprint | Main risk |
|---|---|---|---|
| Option A: narrow public-intake-only port | Roughly 3-5 manifest/policy files: `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`, `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`, `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml` or route-only equivalent, minimal `kustomization.yaml` files if needed, and dev Cedar policy entries. | Reuse/extend existing BL-013 tripwire; add targeted assertions for no local hosts/principals in dev public-intake substrate if not already covered. | Produces a partial dev channel by design; readers may mistake it for full runtime readiness unless docs/tests are explicit. |
| Option B: full template port | Dozens to hundreds of manifest changes plus channel contract/schema and renderer updates. Likely touches every top-level subsystem and may add `gitops/channels/dev/` with a complete tree. | Broad Kustomize build checks, schema checks, local-reference bans, provider-specific bans, policy bundle generation, and render snapshot tests. | Scope creep and premature remote runtime decisions; high chance of coupling BL-013 to unrelated infrastructure questions. |
| Option C: Kustomize base + overlays | Large structural refactor: move common manifests into bases, add local/dev overlays, update paths, update renderer assumptions, and preserve local build output. | Kustomize build parity for local, dev overlay static checks, no-local-value checks, and BL-013 tripwire. | Refactor risk against a known-working local channel; requires careful decomposition before it is safe. |

PROBLEM_MAP_DONE: research/48-init-138-remote-channel-problem-map.md
