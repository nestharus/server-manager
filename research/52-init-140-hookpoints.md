# INIT-140 — Hookpoints (web host rate-limit binding fix)

Source proposal: `proposals/35-init-140-web-host-rate-limit-fix.md`.
Source RCA: `.tmp/init-140-bl-020/phase0/rca.md`.
Source risk gates:
`plans/risk/init-140-{audit,scope,shortcut,supported-surface}.md`.

INIT-140 has a narrow hookpoint surface:

1. Add the missing namespaced
   `KongPlugin/auth-system/public-intake-rate-limit` next to the
   local `Ingress/auth-system/web-public-intake`.
2. Mirror the same `auth-system` plugin in the dev Pomerium
   public-intake manifest.
3. Strengthen the static pytest guard so this bug class cannot
   return: no orphaned `konghq.com/plugins: public-intake-rate-limit`
   references and no silent config drift between duplicated
   `public-intake-rate-limit` plugins.
4. Keep the INIT-139 live-cluster validator as the runtime proof; it
   should move from `8 pass / 1 fail` to `12 pass / 0 fail`.

The root cause is KIC namespace-local plugin lookup. A name-only
`konghq.com/plugins` annotation on an Ingress is resolved in the
Ingress namespace. The web public-intake Ingress is in `auth-system`,
but the only existing local plugin is in `server-manager`; KIC therefore
emits `KongConfigurationTranslationFailed` and creates the web route
with `plugins=[]`.

NOTE: `KongClusterPlugin` centralization remains deferred. That is not
a hookpoint for INIT-140. The supported-surface gate's F2 says to
revisit cluster-scoped centralization only after the copy count grows
enough to justify a separate shared-policy design decision.

---

## H1 — Local `auth-system` KongPlugin manifest

**File to edit:**
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`.

**Current shape:** one document only:
`Ingress/auth-system/web-public-intake`, annotated with
`konghq.com/plugins: public-intake-rate-limit`
(`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml:1-44`).
There is no `KongPlugin` in this file or elsewhere in `auth-system`.

**Hookpoint:** prepend a `KongPlugin` document before the existing
Ingress and separate it with `---`.

Locked manifest block:

```yaml
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: public-intake-rate-limit
  namespace: auth-system
plugin: rate-limiting
config:
  minute: 5
  hour: 50
  policy: local
  fault_tolerant: true
  hide_client_headers: false
---
```

Then leave the existing Ingress document intact:

- `metadata.name: web-public-intake`
- `metadata.namespace: auth-system`
- `metadata.annotations.konghq.com/plugins: public-intake-rate-limit`
- host `web.local.humility.local`
- paths `/api/public/applications`, `/api/public/chapters`,
  `/api/applications`
- backend `pomerium-proxy:80`

This plugin config must match the canonical public-intake rate-limit
config exactly:

```yaml
minute: 5
hour: 50
policy: local
fault_tolerant: true
hide_client_headers: false
```

**Do not change:** Pomerium routes, TLS annotations, path set, backend
service, Ingress name, Ingress namespace, or plugin annotation.

**Why this hook exists:** KIC resolves the existing annotation from
the Ingress namespace, `auth-system`. This resource is the missing
same-namespace object that lets KIC attach the route-scoped Kong
`rate-limiting` plugin to the web public-intake route.

---

## H2 — Dev channel mirror in `auth-system`

**File to edit:**
`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`.

**Current shape:** one document only:
`Ingress/auth-system/web-public-intake`, annotated with
`konghq.com/plugins: public-intake-rate-limit`
(`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml:1-36`).
The dev channel already has the same orphan pattern as local because
its API-side plugin is in `server-manager`, not `auth-system`.

**Hookpoint:** prepend the same `KongPlugin` document as H1, with
`metadata.namespace: auth-system`, before the existing dev Ingress.

Locked manifest block:

```yaml
apiVersion: configuration.konghq.com/v1
kind: KongPlugin
metadata:
  name: public-intake-rate-limit
  namespace: auth-system
plugin: rate-limiting
config:
  minute: 5
  hour: 50
  policy: local
  fault_tolerant: true
  hide_client_headers: false
---
```

Then leave the existing dev Ingress document intact:

- `metadata.name: web-public-intake`
- `metadata.namespace: auth-system`
- `metadata.annotations.konghq.com/plugins: public-intake-rate-limit`
- host `web.dev.humility.gg`
- paths `/api/public/applications`, `/api/public/chapters`,
  `/api/applications`
- backend `pomerium-proxy:80`

**Existing inclusion hooks:** no kustomization edit is expected for
this file. `gitops/channels/dev/kustomization.yaml` already includes
`auth/pomerium/public-intake-rate-limit.yaml`; the local Pomerium
kustomization already includes its matching file.

**Config-drift note from F1:** the current dev API-side
`KongPlugin/server-manager/public-intake-rate-limit` is missing
`policy: local`
(`gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml:1-11`).
Because TG-2 is being strengthened to assert canonical config parity,
implementation must not leave dev in a state where the new
`auth-system` plugin has the canonical config but the dev
`server-manager` plugin does not. The parity test in H3 should expose
that immediately.

---

## H3 — TG-2 pytest: anti-orphan plus config-parity guard

**Primary test hook:** add the TG-2 static guard under `infra/tests/`.
The proposal names a new file:
`infra/tests/test_kong_plugin_orphan_references.py`.

**Existing helper patterns to reuse:**

- `infra/tests/test_public_intake_rate_limit.py:17-23` parses
  multi-document YAML with `yaml.safe_load_all` and stamps
  `_source_path`.
- `infra/tests/test_public_intake_rate_limit.py:53-71` has small
  structural helpers for `metadata`, `annotations`, ingress paths, and
  plugin annotation reads.
- `infra/tests/test_public_intake_channel_tripwire.py:41-46`,
  `:56-74`, and `:132-142` provide the same style for reading channel
  YAML, identifying resources by kind/name/namespace, and producing
  loud assertion failures.

**Current test that must be reconciled:** after H1, local will have two
`KongPlugin` resources named `public-intake-rate-limit` in the parsed
local resources: one in `server-manager`, one in `auth-system`.
`infra/tests/test_public_intake_rate_limit.py:328-345` currently
asserts `len(plugins) == 1` and `namespace == server-manager`.
That assertion must be updated, replaced, or superseded by the new
TG-2 guard. Leaving it unchanged will make the intended manifest fix
fail the existing test suite.

**Guard scope:** parse all source manifests under
`gitops/channels/*/**/*.yaml` that can contain public-intake
`Ingress` or `KongPlugin` resources. Use structured YAML parsing, not
raw substring scans.

For every parsed `Ingress` whose annotation
`metadata.annotations["konghq.com/plugins"]` contains
`public-intake-rate-limit`, assert both:

1. A matching same-channel, same-namespace
   `KongPlugin/public-intake-rate-limit` exists.
2. That plugin's `config` block exactly equals the canonical config.

The annotation parser should treat `konghq.com/plugins` as a
plugin-name list, not as exact raw text. Accept a single name and
comma-separated names so a future annotation like
`public-intake-rate-limit,other-plugin` is still evaluated correctly.

Canonical config:

```python
CANONICAL_PUBLIC_INTAKE_RATE_LIMIT_CONFIG = {
    "minute": 5,
    "hour": 50,
    "policy": "local",
    "fault_tolerant": True,
    "hide_client_headers": False,
}
```

The guard should also assert all `KongPlugin` resources named
`public-intake-rate-limit` in the channel have:

- `plugin == "rate-limiting"`
- `config == CANONICAL_PUBLIC_INTAKE_RATE_LIMIT_CONFIG`

This absorbs supported-surface F1: anti-orphan detection alone catches
missing resources but does not catch config drift. When either the
`server-manager` or `auth-system` copy is changed without the other,
TG-2 must fail until both copies match the canonical reference.

Recommended internal model:

- Build a per-channel index of
  `(namespace, name) -> {"plugin": document, "source": path}` for
  `kind: KongPlugin`.
- Walk every `kind: Ingress`.
- Read `metadata.namespace`; if absent, use only manifests where the
  namespace is explicit for this check. The current four public-intake
  Ingresses all set `metadata.namespace`.
- Split the plugin annotation into names and select ingresses that
  reference `public-intake-rate-limit`.
- Assert `(ingress_namespace, "public-intake-rate-limit")` exists in
  the same channel's plugin index.
- Assert the matched plugin's config equals the canonical config.
- Assert every channel that has both
  `server-manager/public-intake-rate-limit` and
  `auth-system/public-intake-rate-limit` has identical config on both.

Failure messages should include:

- channel
- Ingress namespace/name
- source file for the Ingress
- missing or mismatched plugin namespace/name
- source file for the plugin when it exists
- observed config versus expected canonical config

**Expected source resources after implementation:**

| Channel | Ingress using annotation | Required same-namespace plugin |
|---|---|---|
| `local` | `Ingress/server-manager/server-manager-public-intake-api` | `KongPlugin/server-manager/public-intake-rate-limit` |
| `local` | `Ingress/auth-system/web-public-intake` | `KongPlugin/auth-system/public-intake-rate-limit` |
| `dev` | `Ingress/server-manager/server-manager-public-intake-api` | `KongPlugin/server-manager/public-intake-rate-limit` |
| `dev` | `Ingress/auth-system/web-public-intake` | `KongPlugin/auth-system/public-intake-rate-limit` |

**Tests to run for TG-2:**

```bash
pytest infra/tests/test_kong_plugin_orphan_references.py
pytest infra/tests/test_public_intake_rate_limit.py
pytest infra/tests/test_public_intake_channel_tripwire.py
pytest infra/tests/test_dev_channel_kustomize_build.py
```

The dev kustomize test currently asserts only the existing
`server-manager` plugin, API Ingress, web Ingress, and Pomerium config
are present. It does not need to be the parity guard, but it is a good
post-edit sanity check because H2 changes a file included by
`gitops/channels/dev/kustomization.yaml`.

---

## H4 — TG-1 live-cluster regression note

**Runtime validator:** `infra/tests/validate_kong_kic_translation_local.sh`.

**Current expected failing state from the RCA:**

```text
RESULT: pass=8 fail=1 skip=0
FAIL: missing enabled route-scoped rate-limiting plugin for web.local.humility.local/api/public/applications
```

The failing route diagnostic shows the web public-intake Kong route
with `plugins=[]`. That is the non-vacuous symptom TG-1 must reverse.

**Post-reconcile acceptance:** after GitOps reconciles the local
manifest change from H1, run:

```bash
infra/tests/validate_kong_kic_translation_local.sh --cluster --kubeconfig "$HOME/.kube/humility-local.yaml"
```

The result should flip to:

```text
RESULT: pass=12 fail=0 skip=0
```

The additional successful checks are the three web-host public-intake
paths plus the required adjacent negative route check already in the
validator:

- `web.local.humility.local/api/public/applications`
- `web.local.humility.local/api/public/chapters`
- `web.local.humility.local/api/applications`
- `api.local.humility.local/api/v1/web/admin/chapters` remains without
  a route-scoped `rate-limiting` plugin

TG-1 remains a live-cluster regression note, not a static manifest
replacement. The pytest guard in H3 proves the GitOps structure is not
orphaned or drifted; this validator proves KIC translated that structure
into enabled route-scoped Kong `rate-limiting` plugins on the actual
runtime routes.

HOOKPOINTS_DONE: research/52-init-140-hookpoints.md
