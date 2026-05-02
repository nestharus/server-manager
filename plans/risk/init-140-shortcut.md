# INIT-140 — Shortcut risk gate (web host rate-limit binding fix)

**Verdict:** LOW

Scope: INIT-140 fixes BL-020, where the INIT-139 live cluster validator
finds the `web.local.humility.local` public-intake Kong route but that route
has no enabled route-scoped `rate-limiting` plugin. The proposal adds the
missing same-namespace `KongPlugin/public-intake-rate-limit` beside the
`Ingress/auth-system/web-public-intake` binding for local and dev, plus a
static anti-orphan pytest guard and the existing INIT-139 live validator as
the post-reconcile runtime proof.

This shortcut gate checks two things:

- C1: the proposal ships the right test gates: TG-1 live cluster proof,
  TG-2 anti-orphan-reference pytest, and TG-3 INIT-139 regression coverage.
- C2: the proposal closes the root cause, not just the visible symptom.

Source:
`proposals/35-init-140-web-host-rate-limit-fix.md`,
`.tmp/init-140-bl-020/phase0/rca.md`,
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`,
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`.

## C1 — Right test gates

**Pass.**

TG-1 is the live-cluster gate that matters for this failure class. The RCA's
non-vacuous post-fix proof requires
`infra/tests/validate_kong_kic_translation_local.sh --cluster --kubeconfig "$HOME/.kube/humility-local.yaml"`
to show the `web.local.humility.local` route for
`/api/public/applications`, `/api/public/chapters`, and `/api/applications`
with an enabled route-scoped `rate-limiting` plugin, ending at
`RESULT: pass=12 fail=0 skip=0` (RCA lines 111-123). The proposal carries
that through directly: TG-1 requires the INIT-139 validator after GitOps
reconcile, the result change from `pass=8 fail=1` to `pass=12 fail=0`, route
resolution for all three web public-intake paths, and the
`KongConfigurationTranslationFailed` event clearing or no longer being
re-emitted (proposal lines 148-166).

This rejects the main shortcut: editing the manifests and then declaring
success from YAML shape alone. The failing evidence is runtime KIC translation:
Kong Admin API reports the web route with `plugins=[]` (RCA lines 17-20), so
the gate must continue to prove route-scoped plugins through Kong runtime state.
TG-1 does that.

TG-2 is the right static guard for the newly discovered root-cause class. The
current local manifests demonstrate the orphan shape:

- `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml` declares
  `Ingress/auth-system/web-public-intake` and annotates it with
  `konghq.com/plugins: public-intake-rate-limit` (lines 4-13), but the file
  contains no same-namespace `KongPlugin`.
- `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  declares `KongPlugin/server-manager/public-intake-rate-limit` with the
  canonical `rate-limiting` config (lines 1-12), and the working API Ingress
  references that plugin from the same namespace (lines 14-26).

The proposal's TG-2 requires a pytest guard that fails when an Ingress
references `konghq.com/plugins: public-intake-rate-limit` but the same
channel's parsed or rendered resources do not include
`KongPlugin/<same namespace>/public-intake-rate-limit` (proposal lines
168-177). That is not a duplicate of TG-1; it catches the manifest orphan
before KIC has to diagnose it in a live cluster.

TG-3 keeps INIT-139 as the regression catch instead of replacing it with the
new static test. The proposal requires the existing live runtime gate to remain
the post-fix proof, and says removing either auth-system `KongPlugin` block
from the local live path should make the validator fail again on the web-host
public-intake route with missing route-scoped `rate-limiting` (proposal lines
179-184). That closes the "we added a static guard, so skip the live validator"
shortcut.

**Risk:** the plausible shortcut would be to land only the new
`KongPlugin/auth-system` YAML and a static existence test, while dropping or
softening the INIT-139 runtime check because the manifest now "looks right."
Another shortcut would be a static test that checks only whether a
`KongPlugin/public-intake-rate-limit` exists anywhere in the channel, which
would still pass the broken current local shape because the `server-manager`
plugin exists.

**Mitigation:** TG-1 and TG-3 retain the live Admin API validator, while TG-2
requires same-namespace matching. The three gates are complementary: runtime
translation, pre-runtime orphan detection, and regression protection.

**Implementation note, not a gate blocker:** the TG-2 pytest should parse YAML
documents structurally and treat `konghq.com/plugins` as a plugin-name list,
not a raw-file substring. The proposal's same-namespace contract is clear
enough for the shortcut gate, but the implementation should avoid an exact-text
test that misses comma-separated annotations in future manifests.

## C2 — Closes the actual root cause

**Pass.**

The RCA root cause is explicit: `Ingress/auth-system/web-public-intake`
references `public-intake-rate-limit`; KIC resolves that local
`konghq.com/plugins` value in the Ingress referer's namespace,
`auth-system`; no `KongPlugin/public-intake-rate-limit` exists there; the only
matching plugin exists in `server-manager`; KIC records
`KongConfigurationTranslationFailed`, skips the unresolved association, and
emits the Kong route with `plugins=[]` (RCA lines 99-103).

The proposal fixes that namespace lookup failure directly. Q1 locks Option A:
copy `KongPlugin/public-intake-rate-limit` into `auth-system` for every channel
that has `Ingress/auth-system/web-public-intake`, so the server-manager Ingress
continues resolving against `KongPlugin/server-manager/...` and the auth-system
Ingress resolves against `KongPlugin/auth-system/...` (proposal lines 37-48).
Q2 places the local `auth-system` plugin in the same file as the existing
`web-public-intake` Ingress, with the reference and definition moving together
(proposal lines 68-78). Q3 mirrors the fix to the dev channel because INIT-138
created the same `auth-system` web Ingress pattern there (proposal lines
80-89). Q4 pins the copied plugin to the canonical `rate-limiting` config used
by the working `server-manager` plugin: `minute=5`, `hour=50`, `policy=local`,
`fault_tolerant=true`, and `hide_client_headers=false` (proposal lines 91-112).

This is a root-cause fix, not symptom suppression. The proposal does not relax
the INIT-139 validator, remove the `konghq.com/plugins` annotation, move the
web route out of Pomerium, change route matching, or substitute request-burst
behavior for Admin API route/plugin inspection. The anti-scope explicitly
keeps KongClusterPlugin migration, cross-namespace reference adoption,
Pomerium route reconfiguration, request-burst behavior testing, and
Discord-visible actions out of this slice (proposal lines 186-198). Those
exclusions are coherent because the root cause is namespace-local KIC plugin
resolution, not Pomerium routing or rate-limit semantics.

**Risk:** the shortcut would be to make the failing validator green by changing
the route set, skipping the web-host path, looking for a plugin anywhere in
Kong rather than on the selected route, or adding a broad cluster/global plugin
that hides the orphan reference without fixing the Ingress-local plugin
association. Another shortcut would be to add a plugin in `auth-system` with a
different config, creating a green translation check but divergent public-
intake behavior.

**Mitigation:** the proposal's substrate requires the same-namespace
`KongPlugin` in `auth-system` while preserving the existing Ingress paths and
annotation unchanged (proposal lines 118-125), and requires exact config parity
with the canonical `server-manager` plugin. TG-1 then proves KIC translated the
binding into an enabled route-scoped Kong `rate-limiting` plugin on the actual
web public-intake route.

## Verdict

**LOW.** The proposal is not taking the shortcut path. It preserves the live
runtime validator as the authoritative proof, adds the missing static guard for
same-namespace plugin references, and fixes the namespace-local lookup failure
identified by the RCA instead of weakening the failing check.

No proposal revision is required for the shortcut gate.

GATE_SHORTCUT_DONE: plans/risk/init-140-shortcut.md
