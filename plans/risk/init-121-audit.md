READ:
- proposals/03-cedar-policy-source.md
- research/04-cedar-policy-source-problem-map.md
- .tmp/rca/cedar-bootstrap-put-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md

## Inputs read

- Proposal: `proposals/03-cedar-policy-source.md`
- Problem map: `research/04-cedar-policy-source-problem-map.md`
- RCA: `.tmp/rca/cedar-bootstrap-put-FINDINGS.md`
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`

## Checklist results

| Item | Status | Citation | Audit finding |
|---|---|---|---|
| 1. Net-value statement | PRESENT | `proposals/03-cedar-policy-source.md:33-35`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` | The proposal includes a qualitative positive net-value statement. It names the concrete current-state risk from the RCA/problem map, limits added blast radius to OPAL/Cedar manifests, seed snapshot, bundle materialization, and validators, and states why migration burden is justified. |
| 2. Scope and Anti-scope sections | PRESENT | `proposals/03-cedar-policy-source.md:37-58`; proposal sufficiency rule at `/home/nes/ai/workflows/implementation-pipeline.md:86-87` | Scope and anti-scope are explicit. Scope covers OPAL source config, client updater posture, seed snapshot changes, `.cedar` materialization, removal of ConfigMap/Job, and validator replacements. Anti-scope excludes Authentik, Pomerium, public-intake semantics, API Cedar call sites, tenant redesign, remote apply, new bundle services, and dual loading fallback. |
| 3. Supported-surface track | PRESENT | `proposals/03-cedar-policy-source.md:177-191`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88` | The track covers deployment mode (`179`), customer cohort (`181`), adjacent public/user-reachable paths (`183`), blast-radius notes for unchanged adjacent paths (`185`), migration path (`187`), rollback path (`189`), and observability (`191`). |
| 4. Assumption register | PRESENT | `proposals/03-cedar-policy-source.md:193-203`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:91` | A1 through A5 each state evidence and an invalidation source. The assumptions cover OPAL cloning, `.cedar` file identity/loading behavior, canonical policy count handling, Flux unaffected by top-level `policy/`, and semantic equivalence after ConfigMap/Job removal. |
| 5. Test-intent track | PRESENT | `proposals/03-cedar-policy-source.md:205-219`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:92` | T1 through T7 each include change risk, intended behavior, selected level, fixture source, assumption link, expected observable signal, and residual risk. The track covers static seeded-source equality, manifest authority, runtime policy hydration, access-policy decisions, tenant isolation, public-intake fixture preservation, and post-polling hydration durability. |
| 6. Contracts/migrations | PRESENT | OPAL server env and repo config: `proposals/03-cedar-policy-source.md:74-85`; OPAL client env posture: `87-97`; seed snapshot and bundle materialization contract: `103-135`; manifest removal contract: `137-146`; migration and rollback order: `225-243` | New/changed manifest and environment contracts are concrete. The proposal names exact OPAL repo URL, policy extension handling, polling cadence, Cedar store env vars, generated `.cedar` path pattern, invalid JSON/ID failure cases, stale generated-file deletion behavior, Kustomization removals, and operational migration/rollback order. No API schema or database migration is introduced in scope. |
| 7. Residual-risk artifact path named | PRESENT | `proposals/03-cedar-policy-source.md:221-223`; Step 6b residual rule at `/home/nes/ai/workflows/implementation-pipeline.md:163-167` | The proposal explicitly requires `plans/risk/init-121-test-residuals.md` if any named test-intent risk cannot be verified, and lists the residual fields required by the pipeline. |
| 8. Out-of-scope follow-up | PRESENT | `proposals/03-cedar-policy-source.md:245-250` | The proposal lists explicit follow-ups: remote channel apply, stronger arbitrary restart durability if not included in Step 6b, telemetry/audit dashboards/alerts, public-intake/Pomerium/rate-limit/application behavior changes, and multi-service or multi-channel bundle partitioning. |

## Notable observations

- The proposal is audit-complete for Phase 3 presence obligations. I found no missing checklist area that would block Phase 4 on audit grounds.
- The residual-risk artifact path uses this repo's `plans/risk/init-121-test-residuals.md` location rather than the global pipeline's example `risk/NN-test-residuals.md`. Because the invoking task itself writes Phase 4 outputs under `plans/risk/`, this is a concrete named path, not an audit failure.
- The contracts/migrations section is sufficient for audit risk: the proposal does not introduce API schemas or database migrations, and the OPAL env-var, GitOps manifest, seed snapshot, generated policy file, and validator contract changes are specific enough for Step 6a.

## Verdict

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
