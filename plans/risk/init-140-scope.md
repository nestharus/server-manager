# INIT-140 Scope risk gate

Verdict: **PASS / LOW**

Reviewed:

- `proposals/35-init-140-web-host-rate-limit-fix.md`
- `.tmp/init-140-bl-020/phase0/rca.md`
- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`

## Gate answers

- Is the change minimal? **Y**
- Are there other ingresses with the same orphan reference pattern that we'd miss? **N**, not if the proposal covers both local and dev Pomerium public-intake manifests and the static guard scans all channel resources for same-namespace `KongPlugin` resolution.
- Is the dev channel mirror in scope or out of scope? **In scope**, but only for the same `auth-system` `KongPlugin/public-intake-rate-limit` mirror needed by the already-materialized dev `web-public-intake` Ingress.

## Findings

### 1. Minimality is acceptable — PASS

The RCA identifies a single failure mode: `Ingress/auth-system/web-public-intake`
references `konghq.com/plugins: public-intake-rate-limit`, but KIC resolves
namespaced `KongPlugin` references in the Ingress referer's namespace. In local,
the only existing `KongPlugin/public-intake-rate-limit` is in
`server-manager`, so the `auth-system` Ingress reference is orphaned.

The proposal's selected fix is the smallest direct repair for that mechanism:
add a same-name `KongPlugin` in the Ingress namespace, next to the Ingress that
references it. It does not move routes, alter Pomerium behavior, change hosts or
paths, introduce `KongClusterPlugin`, or add cross-namespace reference machinery.

The declared production surface is bounded to two GitOps files:

- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`

The new pytest guard is also scope-appropriate because it encodes the exact
KIC namespace-resolution contract that failed: every Ingress with
`konghq.com/plugins: public-intake-rate-limit` must have a same-channel,
same-namespace `KongPlugin/public-intake-rate-limit`.

### 2. No uncovered same-pattern ingress remains — PASS

Repository source manifests under `gitops/channels`, excluding rendered output,
currently have four public-intake plugin references:

- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  - `Ingress/auth-system/web-public-intake`
  - references `public-intake-rate-limit`
  - same-channel plugin exists only as `server-manager/public-intake-rate-limit`
  - status: **orphan**
- `gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml`
  - `Ingress/auth-system/web-public-intake`
  - references `public-intake-rate-limit`
  - same-channel plugin exists only as `server-manager/public-intake-rate-limit`
  - status: **orphan**
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  - `Ingress/server-manager/server-manager-public-intake-api`
  - references `public-intake-rate-limit`
  - same-file `KongPlugin/server-manager/public-intake-rate-limit` exists
  - status: **not orphaned**
- `gitops/channels/dev/applications/server-manager/public-intake-rate-limit.yaml`
  - `Ingress/server-manager/server-manager-public-intake-api`
  - references `public-intake-rate-limit`
  - same-file `KongPlugin/server-manager/public-intake-rate-limit` exists
  - status: **not orphaned**

The proposal covers both orphaned references and leaves the already-resolved
API-side references alone. A test scoped to all channel GitOps resources with
the `konghq.com/plugins: public-intake-rate-limit` annotation will catch this
class without needing to know the specific Ingress names.

### 3. Dev channel mirror is correctly in scope — PASS

The dev channel already contains the same source-level pattern as local:
`Ingress/auth-system/web-public-intake` in
`gitops/channels/dev/auth/pomerium/public-intake-rate-limit.yaml` is annotated
with `konghq.com/plugins: public-intake-rate-limit`, while the dev
`KongPlugin/public-intake-rate-limit` exists only in `server-manager`.

Including dev does not broaden the change into full dev-channel readiness. It
only mirrors the same namespace-local `KongPlugin` required for a manifest that
already exists. If dev were left out, the proposed static anti-orphan guard
would either fail immediately or have to be narrowed in a way that deliberately
misses an existing copy of the same bug.

### 4. Scope boundary to preserve during implementation — PASS with note

The proposal's Q4 config parity lock says the added `auth-system` plugin config
must match the canonical public-intake settings:

```yaml
plugin: rate-limiting
config:
  minute: 5
  hour: 50
  policy: local
  fault_tolerant: true
  hide_client_headers: false
```

That is in scope for the new `auth-system` plugin blocks. It should not be used
as permission to expand the diff into unrelated normalization of existing
API-side dev manifests unless the proposal is revised, because the declared
diff budget only authorizes the two Pomerium GitOps files plus one static test.

## Conclusion

Scope risk is LOW. The proposal fixes the exact namespace-local orphan
reference found by the RCA, includes the only other source manifest with the
same orphan pattern, and keeps the dev mirror limited to an already-existing
public-intake Ingress. No Pomerium route redesign, cluster-scoped plugin
migration, cross-namespace reference system, runtime burst test, or broader dev
channel materialization is in scope.

GATE_SCOPE_DONE: plans/risk/init-140-scope.md
