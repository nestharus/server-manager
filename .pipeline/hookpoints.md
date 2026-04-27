# INIT-118 Phase 5 Hookpoints

## Reuse Points

- `forms/dark-nemesis.yaml` is the initial public form schema.
- `services/api/app/api/v1/router.py` remains the API router hookpoint.
- `services/api/app/repositories/chapters.py` establishes the chapter table and
  aggregate-head join shape reused by the web admin list.
- `gitops/channels/local/applications/server-manager` provides the raw-manifest
  application pattern.
- `gitops/channels/local/auth/pomerium` owns Pomerium routes and ingress.
- `infra/tests/validate_*_local.sh` provides the pass/fail/skip harness shape.
- `.buildkite/pipeline.yml` already carries INIT static checks and image builds.

## Collisions

- Solid 2 beta no longer exposes Solid 1-compatible `solid-js/web`; Vite and
  current adapters still expect older export shapes. INIT-118 records this as a
  compatibility gate and isolates it in `services/web/src/solid-compat`.
- `.refs/ui-designer/` is dated reference material and must not steer the design.
- Existing `server-manager` namespace remains API/Discord-owned; the SPA uses a
  separate `web` namespace so `kubectl get pods -n web` is unambiguous.

## Deletion Candidates

None in production code. Future work can delete compatibility files once the
Solid 2 ecosystem packages natively target the new exports.

## Implementation Blockers

No hard blockers. Cluster runtime proof requires a live local k3d channel,
registry, Pomerium, and Authentik credentials. Non-cluster proof is sufficient
for static CI.
