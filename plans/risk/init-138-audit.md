# INIT-138 Audit Risk

Risk: LOW.

## Verdict

PASS. Proposal 33 commits to a manifest-only, narrow public-intake substrate
port for the `dev` channel, scoped exactly to what the BL-013 tripwire
(`infra/tests/test_public_intake_channel_tripwire.py`) validates. All seven
audit checks are satisfied at the proposal level. Implementation may proceed.

## Audit checks

### 1. All 4 substrate items materialized for dev — PASS

Proposal §3 enumerates the exact files BL-013 keys on:

- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
  (KongPlugin + API ingress).
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml` (web ingress).
- `gitops/channels/dev/auth/pomerium/secrets-infisicalsecret.yaml` (Pomerium
  routes block under `managedSecretReference.template.data.config.yaml`).
- `policy/cedar/channels/dev/services/server-manager-api/policies.json` (append
  `public-intake-allow` and `public-intake-no-read`).

A fifth file, `gitops/channels/dev/kustomization.yaml`, is added only as a
direct-reference build entrypoint (TG-4); not required by the tripwire and not
in violation of anti-scope.

### 2. Channel-derived hostnames + principals — PASS

Proposal Q2 locks `api.dev.humility.gg`, `web.dev.humility.gg`,
`protected-api.dev.humility.gg`, `authenticate.dev.humility.gg`, and
`auth.dev.humility.gg/application/o/pomerium/`. Q2 explicitly bans
`*.local.humility.local`, `web-intake.local`, `Service::"*.local"`,
`/auth/local/...`, local Step CA issuers, local TLS secret names, and local
DNS aliases. The Kubernetes-internal `.svc.cluster.local` suffix is correctly
exempted — that is the upstream the BL-013 parser expects
(`server-manager-web.web.svc.cluster.local:8080`).

### 3. Cedar policy uses Public::"web-intake.dev" — PASS

Proposal Q3 specifies the principal as `Public::"web-intake.dev"` for both
policies, retaining canonical IDs `public-intake-allow` and
`public-intake-no-read` (the IDs the tripwire's `_validate_cedar_policies`
keys on at lines 285–298 of the test). TG-3 acceptance includes a literal
check that `Public::"web-intake.local"` is absent.

### 4. Pomerium routes target dev hostnames — PASS

Proposal Q4 + §3 specify route `from` sources of
`https://web.dev.humility.gg` and `https://protected-api.dev.humility.gg`,
identity-bearing web routes ordered before the public catch-all, and the
catch-all `to` of `http://server-manager-web.web.svc.cluster.local:8080`.
This matches the tripwire's `_validate_pomerium_routes` exactly: it requires
identity-route-index < public-route-index for `from: https://web.<channel>.humility.gg`
where the public route's `to` is `WEB_UPSTREAM`.

### 5. BL-013 tripwire passes for the new dev channel — PASS (proposal-level)

Each tripwire validator's expectations are met by the proposal:

- `_validate_api_rate_limit`: KongPlugin `public-intake-rate-limit` in
  `server-manager`; Ingress `server-manager-public-intake-api` with
  `konghq.com/plugins: public-intake-rate-limit`, host `api.dev.humility.gg`,
  paths `/api/v1/public/applications` and `/api/v1/public/chapters`,
  backend `server-manager-api:8000`. Matched.
- `_validate_pomerium_rate_limit`: Ingress `web-public-intake` in
  `auth-system`, host `web.dev.humility.gg`, paths `/api/public/applications`,
  `/api/public/chapters`, `/api/applications`, backend `pomerium-proxy:80`,
  kong plugin annotation. Matched.
- `_validate_cedar_policies`: policy IDs `public-intake-allow` (permit) and
  `public-intake-no-read` (forbid); each containing
  `Public::"web-intake.dev"`, the right Action::, the right Resource::.
  Matched (Q3).
- `_validate_pomerium_routes`: secrets manifest with
  `managedSecretReference.template.data.config.yaml`, embedded routes list,
  identity-bearing route before public catch-all on
  `https://web.dev.humility.gg`, public catch-all `to` of
  `http://server-manager-web.web.svc.cluster.local:8080`. Matched.

Proposal §4 TG-1 explicitly enumerates these acceptance criteria. Final
green/red status will only be observable after implementation; the proposal
contract is self-consistent with the tripwire.

### 6. NO Vultr-runtime claims — PASS

Proposal §1 ("not a full remote runtime, a full channel template, or a Vultr
apply"), §2 Q1 ("not a runnable remote server-manager deployment"), and §5
("Do not apply anything to Vultr, Flux, Kubernetes, DNS, or certificate
issuers. This proposal is manifest authoring and static validation only.")
all keep this strictly manifest-only. The InfisicalSecret manifest is
explicitly tagged as static-validation-only with no invented runtime
contract.

### 7. Anti-scope items honored — PASS

Proposal §5 lists comprehensive exclusions:

- No dev Flux wiring, gitops contract block, remote Git source rendering,
  SOPS bootstrap, Cloudflare records, ACME issuer, or LB verification.
- No port of Authentik, MinIO/object-storage runtime, Postgres CNPG, Atlas,
  OPAL, Pomerium proxy deployment, server-manager API/web deployments,
  Buildkite, app-clusters, tenant isolation, observability, or security
  policies beyond the public-intake substrate.
- No template refactor, Kustomize base/overlay system, renderer changes,
  shims, feature flags, dual-host support, or fallback principals.
- No local channel modification.

Diff budget §6 caps the change at 4 added files + 1 Cedar policy update + 0
test changes preferred (with a tightly-bounded exception). Aligned with
audit expectations.

## Notes for implementation

- The tripwire only validates `host: api.<channel>.humility.gg` paths against
  expected paths; it does not validate the KongPlugin's `config.policy`
  field, so omitting `policy: local` from the API-side KongPlugin (Q4) is
  safe.
- Tripwire discovery (`_is_public_intake_relevant`) triggers as soon as
  `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
  is committed; partial materialization will cause the tripwire to fail
  loudly until all four substrate items are in place. Land them as one slice.
- Cedar dev `policies.json` currently contains three entries
  (`dev-server-manager-api-user-read`, `...buildkite-deploy`,
  `dev-cluster-api-crossplane-reconcile`). Append, do not replace.

AUDIT_DONE: plans/risk/init-138-audit.md
