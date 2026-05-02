# Proposal 35 - INIT-140: Web host rate-limit binding fix

## 1. Problem statement

INIT-139's live cluster validator fails for
`web.local.humility.local/api/public/applications` because the Kong route that
handles the three web public-intake paths has no route-scoped `rate-limiting`
plugin.

The failing route is the `web.local.humility.local` route with paths
`/api/public/applications`, `/api/public/chapters`, and `/api/applications`.
Kong Admin API reports that route with `plugins=[]`, while the same validator
finds enabled route-scoped `rate-limiting` plugins on the API-host public
intake routes. The current INIT-139 result is therefore `8 pass / 1 fail`,
with the fail on the web public-intake route.

Root cause: `Ingress/auth-system/web-public-intake` references
`public-intake-rate-limit` through `konghq.com/plugins`, so KIC resolves that
plugin in the Ingress referer's namespace, `auth-system`. No
`KongPlugin/public-intake-rate-limit` exists in `auth-system`; the only local
matching `KongPlugin` exists in `server-manager`. KIC records
`KongConfigurationTranslationFailed` for `ingress/web-public-intake`, skips the
unresolved plugin association, and emits the Kong route without a route-scoped
plugin.

Kong's KIC annotation docs define `konghq.com/plugins` as the annotation that
associates named `KongPlugin` resources with Ingress rules. The KIC CRD docs
also distinguish namespaced `KongPlugin` from cluster-level
`KongClusterPlugin`, which matters because this fix is choosing a namespaced
copy rather than a shared cluster-scoped resource:

- <https://developer.konghq.com/kubernetes-ingress-controller/reference/annotations/#konghqcomplugins>
- <https://developer.konghq.com/kubernetes-ingress-controller/reference/custom-resources/#kongplugin>

## 2. Decisions

### 2.1 Q1. Plugin resolution mechanism

Lock: Option A, copy `KongPlugin/public-intake-rate-limit` into the
`auth-system` namespace for every channel that has the
`Ingress/auth-system/web-public-intake` binding.

This keeps KIC plugin resolution local to the Ingress namespace:

- `Ingress/server-manager/server-manager-public-intake-api` resolves
  `public-intake-rate-limit` against `KongPlugin/server-manager/public-intake-rate-limit`.
- `Ingress/auth-system/web-public-intake` resolves
  `public-intake-rate-limit` against `KongPlugin/auth-system/public-intake-rate-limit`.

#### Trade-offs

Option A adds one small resource per affected channel namespace. That is the
right trade for this bug: it fixes the orphan reference directly, keeps review
and rollback scoped to the channel manifest that owns the binding, and avoids
introducing a shared cluster-level public-intake policy object.

Option B, converting to `KongClusterPlugin`, would remove namespace-local
copies, but it creates a cluster-scoped resource for a use case that is still
channel-specific. That broadens blast radius and makes accidental reuse easier.
Defer this until multi-namespace use is common enough to justify an explicit
cluster-scoped policy decision.

Option C, cross-namespace reference via `ReferenceGrant` or the current KIC
equivalent, is also deferred. It depends on KIC version behavior and adds a new
authorization pattern where the minimal safe fix is a same-namespace
`KongPlugin`.

### 2.2 Q2. Local manifest location

Lock: extend
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` to include
the `KongPlugin` resource block alongside the existing
`Ingress/auth-system/web-public-intake`.

The `KongPlugin` block should be prepended before the existing Ingress and
separated with `---`. Keeping the same file as the binding gives a single
review surface: the plugin reference and the namespace-local plugin definition
move together.

### 2.3 Q3. Dev channel mirror

Lock: apply the same fix to
`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`.

INIT-138 materialized the dev web public-intake Ingress with
`konghq.com/plugins: public-intake-rate-limit`, and that Ingress is also in
`auth-system`. The same namespace-local lookup gap therefore exists in dev.
The dev channel should get the `auth-system` `KongPlugin` in the same file as
the dev `web-public-intake` Ingress.

### 2.4 Q4. KongPlugin config parity

Lock: the `auth-system` plugin config must match the canonical
`server-manager` plugin settings exactly:

```yaml
plugin: rate-limiting
config:
  minute: 5
  hour: 50
  policy: local
  fault_tolerant: true
  hide_client_headers: false
```

This preserves one public-intake rate-limit semantic regardless of whether the
request matches the API-host Ingress or the Pomerium/web-host Ingress.

Implementation note: the local `server-manager` manifest already has the full
canonical config. The dev API-side `server-manager` manifest should be checked
during implementation because it currently exists and is part of the mirrored
surface; the intended config pin for this proposal is the block above.

## 3. Substrate

### Modified file

- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  - Prepend `KongPlugin/public-intake-rate-limit`.
  - Set `metadata.namespace: auth-system`.
  - Use plugin type `rate-limiting`.
  - Use config `minute=5`, `hour=50`, `policy=local`,
    `fault_tolerant=true`, and `hide_client_headers=false`.
  - Keep the existing `Ingress/auth-system/web-public-intake` paths and
    annotation unchanged.

### Modified file

- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`
  - Prepend the same `KongPlugin/public-intake-rate-limit` block.
  - Set `metadata.namespace: auth-system`.
  - Keep the existing dev host `web.dev.humility.gg`, paths, backend, and
    `konghq.com/plugins: public-intake-rate-limit` annotation unchanged.

### New test file

- `infra/tests/test_kong_plugin_orphan_references.py`
  - Parse relevant channel GitOps YAML.
  - For any Ingress with
    `konghq.com/plugins: public-intake-rate-limit`, require a
    same-namespace `KongPlugin/public-intake-rate-limit` in the parsed channel
    resources.
  - Fail with the channel, Ingress name/namespace, plugin name, and source file
    when an orphan reference is found.

## 4. Test plan

### TG-1: live cluster KIC translation

Run the INIT-139 validator against humility-local after GitOps reconciles:

```bash
infra/tests/validate_kong_kic_translation_local.sh --cluster --kubeconfig "$HOME/.kube/humility-local.yaml"
```

Acceptance:

- the result changes from `RESULT: pass=8 fail=1 skip=0` to
  `RESULT: pass=12 fail=0 skip=0`;
- `web.local.humility.local/api/public/applications`,
  `web.local.humility.local/api/public/chapters`, and
  `web.local.humility.local/api/applications` resolve to routes with an enabled
  route-scoped plugin named `rate-limiting`;
- the `KongConfigurationTranslationFailed` event on
  `ingress/web-public-intake` clears or is no longer re-emitted after
  reconciliation.

### TG-2: static anti-orphan pytest guard

Add a pytest guard that fails when an Ingress references
`konghq.com/plugins: public-intake-rate-limit` but the same channel's rendered
or parsed resources do not include
`KongPlugin/<same namespace>/public-intake-rate-limit`.

This is a manifest-structure test, not a runtime translation test. It should
catch the exact class of bug found by the RCA before the cluster validator has
to diagnose it.

### TG-3: validator regression catch

Keep `infra/tests/validate_kong_kic_translation_local.sh` as the post-fix live
runtime gate. If either auth-system `KongPlugin` block is later removed from
the local live path, the validator should again fail on the web-host
public-intake route with missing route-scoped `rate-limiting`.

## 5. Anti-scope

- KongClusterPlugin migration. Deferred until multi-namespace use cases
  proliferate enough to justify a cluster-scoped shared rate-limit resource.
- ReferenceGrant or Kong-specific cross-namespace reference adoption. Deferred
  because it is KIC-version-dependent and unnecessary for the minimal
  namespace-local fix.
- Pomerium route reconfiguration. The failing behavior is KIC plugin
  resolution, not Pomerium routing or upstream path selection.
- Request-burst behavior testing. INIT-139's Admin API validator is the
  required runtime proof for this slice.
- Discord-visible actions. This proposal only changes GitOps manifests and
  tests.

## 6. Diff budget

- 2 GitOps files modified:
  - `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`;
  - `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`.
- About 13 lines added per GitOps file for the `KongPlugin` block plus
  document separator.
- 1 new pytest file, about 30 lines, for the same-namespace anti-orphan
  reference guard.

PROPOSAL_DONE: proposals/35-init-140-web-host-rate-limit-fix.md
