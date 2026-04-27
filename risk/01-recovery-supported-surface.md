Verdict: LOW
TerminationSignal: NONE

# Supported-surface risk — recovery test-first proposal (`proposals/01-recovery-test-first.md`)

Date: 2026-04-27
Assessor: claude-opus (supported-surface, R1)
Inputs: `proposals/01-recovery-test-first.md`,
`risk/01-recovery-audit.md`, `risk/01-recovery-scope.md`,
`risk/01-recovery-shortcut.md`,
`research/01-rca-crossplane-webhook-unreachable.md`,
`research/02-coverage-audit-init-100-118.md`,
`plans/process-tree-audits/init-100-119-process-tree-audit.md`.

## Termination signal evaluation (orthogonal, evaluated FIRST and IN ORDER)

Per `~/ai/workflows/implementation-pipeline.md` Phase 4 rule: supported-surface
termination is orthogonal to the LOW/MEDIUM/HIGH verdict. Evaluated in order:
INVALIDATED_ASSUMPTION first, then NON_POSITIVE_VALUE. "A LOW supported-surface
verdict with a non-positive value signal still terminates."

### T1 — INVALIDATED_ASSUMPTION → does not fire

The most load-bearing assumption that could collapse the current problem framing
is **A1** (Crossplane RCA hypothesis): "INIT-117 NetworkPolicy isolates webhook
ingress in Crossplane and same-pattern operator namespaces"
(`proposals/01-recovery-test-first.md:1121`). If A1 is wrong, SLICE-R.01 (and
the cluster-runtime dependency it unlocks for SLICE-R.10, SLICE-R.11, SLICE-R.21)
collapses.

The proposal acknowledges this and routes correctly to research re-entry rather
than smuggling in a code fix:

- A1 invalidating signal: "SLICE-R.01 tests-first reachability still fails
  after removing or correcting policy isolation, revealing a different failure
  mode" (`proposals/01-recovery-test-first.md:1121`).
- A1 consequence: "Stop SLICE-R.01 and return to RCA before code changes"
  (`proposals/01-recovery-test-first.md:1121`).
- SLICE-R.01 binds Step 6c only to test-derived evidence: Step 6b must "prove
  webhook endpoint reachability, admission dry-run behavior, and absence of
  unintended same-namespace isolation" *before* Step 6c "applies the minimal
  NetworkPolicy adjustment" (`proposals/01-recovery-test-first.md:472`-`proposals/01-recovery-test-first.md:481`).
- Phase 5 hookpoint handoff requires mapping rendered webhook Services and
  admission dry-run commands before Phase 6 starts
  (`proposals/01-recovery-test-first.md:1166`-`proposals/01-recovery-test-first.md:1169`).
- The RCA's Candidates A and B are both rated `high` confidence (RCA lines
  312-345) with mutually-reinforcing evidence (NetworkPolicy selector + iptables
  `REJECT` + node-local accept rule + observability-namespace traversal
  succeeding). Even if A1 is invalidated, the consequence is bounded to
  SLICE-R.01 — it does not collapse SLICE-R.02 (CI service-suite wiring),
  SLICE-R.04 (captured pytest rewrite), SLICE-R.05..R.09/R.12..R.13 (CONTINUE
  layers whose validators do not depend on Crossplane webhook readiness), or
  SLICE-R.24/R.25.

The other assumptions with potential research-re-entry implications also have
explicit invalidation paths:

- **A2** (`proposals/01-recovery-test-first.md:1122`): if proposal text is too
  vague to derive contract → escalate to user; do not let Step 6b guess.
- **A7** (`proposals/01-recovery-test-first.md:1127`): if user/DECISIONS.md
  changes deployment target before Phase 6 starts → return to Phase 2.5 problem
  map and supported-surface risk. The current
  `MEMORY.md`/`environment-agnostic-stack.md` posture and Phase 5 in-progress
  status (INIT-008..016 with local verification only) both affirm local k3d as
  the supported surface as of 2026-04-27. No invalidation evidence is in scope.
- **A8** (`proposals/01-recovery-test-first.md:1128`): if E2E harness encodes
  broken WIP assumptions → decompose SLICE-R.23 further.

No assumption invalidation breaks the current problem framing. → INVALIDATED_ASSUMPTION
does not fire.

### T2 — NON_POSITIVE_VALUE → does not fire

The recovery's value must be observable on the current supported surface (local
k3d, `humility-local` cluster). Each value lever is locally observable without
real Vultr deployment:

- **Crossplane webhook repair (SLICE-R.01)**: the failure mode is reproducible
  only on local k3d (RCA lines 7-19, 35-48). Real Vultr/VKE uses Cilium, not
  k3s embedded kube-router; the bug shape is k3d-specific. Repair value is
  fully visible on the supported surface.
- **Service-suite CI promotion (SLICE-R.02)**: the coverage audit identifies
  25+ `services/api/tests/` files as DEAD/VERIFIED — they exercise real Postgres
  via testcontainers and httpx against FastAPI; no remote cluster is required.
  Wiring them into `.buildkite/pipeline.yml` is a CI-lane change visible
  immediately.
- **CAPTURED rewrite (SLICE-R.04)**: replacing
  `infra/tests/test_*_contract.py` literal-mirror assertions with proposal-
  derived behavior is pure local pytest work; no cluster needed.
- **Runtime validator promotion (SLICE-R.03, SLICE-R.05..R.17)**: the
  DEAD/VERIFIED validators (`validate_object_storage_local.sh`,
  `validate_tls_dns_local.sh`, `validate_app_clusters_local.sh`,
  `validate_cluster_security_local.sh`,
  `validate_container_delivery_local.sh`) already produce evidence against
  local k3d. Proposal observes "57 pods Running and the Infisical bootstrap
  path reaching `ReadyToSyncSecrets=True`"
  (`proposals/01-recovery-test-first.md:54`-`proposals/01-recovery-test-first.md:55`).
  The 180-minute cluster lane already exists per A5.
- **Aggregate proof (SLICE-R.23 / aggregate)**: "run `infra/tests/e2e/run-fullstack.sh`
  against a clean local cluster. All 19+ cross-cutting tests must pass with
  VERIFIED contracts" (`proposals/01-recovery-test-first.md:1054`-`proposals/01-recovery-test-first.md:1057`).
- **Buildkite blocking gates (SLICE-R.24)**: pure CI verdict-grep + exit-code
  emission, locally observable.
- **Legacy test classification (SLICE-R.25)**: pure file-level disposition;
  local-pytest-observable.

Risk reduced is concrete and current-state on the local surface: false
confidence from CAPTURED tests, Crossplane webhook isolation blocking bring-up,
31% of test files not run at all, 19 INITs with broken Phase 6 firstness,
security/policy surfaces relying on resolver literals
(`proposals/01-recovery-test-first.md:1062`-`proposals/01-recovery-test-first.md:1065`).

Blast radius is bounded internal: "time investment; CI lane changes; churn on
per-INIT validators; deletion or rewrite of captured tests; possible code
changes where independent tests expose real mismatches; more Buildkite runtime
cost for cluster-equipped validation"
(`proposals/01-recovery-test-first.md:1067`-`proposals/01-recovery-test-first.md:1070`).
No user-visible runtime change; anti-scope blocks Discord-visible writes,
INIT-120+ product UI surfaces, and remote apply
(`proposals/01-recovery-test-first.md:1105`-`proposals/01-recovery-test-first.md:1108`).

Net value is positive on the current supported surface. The proposal also
explicitly names the negative-value trigger as a return-to-Phase-2.5 condition
rather than a residual: "Phase 4 supported-surface risk finds that local-first
validation is no longer the supported deployment target or that CI cost prevents
routine use" (`proposals/01-recovery-test-first.md:1098`-`proposals/01-recovery-test-first.md:1100`).
Neither precondition holds today (local k3d is the active platform; cluster lane
already exists at 180 minutes per A5).

→ NON_POSITIVE_VALUE does not fire.

**Termination signal: NONE.** Proceed to verdict.

## Findings table

| # | Severity | Title | Proposal cite | Assumption-register cite |
|---|---|---|---|---|
| SS1 | LOW | Supported surface is local-first; proof target is a clean local k3d cluster driven by the existing local channel — matches `humility-local` posture exactly. | `proposals/01-recovery-test-first.md:70`-`proposals/01-recovery-test-first.md:82`, `proposals/01-recovery-test-first.md:1072`-`proposals/01-recovery-test-first.md:1076`, `proposals/01-recovery-test-first.md:1054`-`proposals/01-recovery-test-first.md:1057` | A7 (`proposals/01-recovery-test-first.md:1127`) |
| SS2 | LOW | Net-value reduction outweighs blast radius. Risk reduced is concrete (Crossplane bring-up unblocked, DEAD/CAPTURED tests promoted/rewritten, security/policy literals replaced with contract tests, blocking Buildkite gates added). Blast radius is internal CI churn and validator rewrites. Migration is in-place per slice; rollback is per-slice git revert. | `proposals/01-recovery-test-first.md:1062`-`proposals/01-recovery-test-first.md:1086` | — |
| SS3 | LOW | Adjacent operator-webhook namespaces (CNPG, cert-manager) are now bound into SLICE-R.01 contract — the namespace surface is "`crossplane-system`, `cnpg-system`, `cert-manager`, and any other namespace where the same INIT-117 policy pattern was applied". Resolves prior-round MEDIUM. | `proposals/01-recovery-test-first.md:466`-`proposals/01-recovery-test-first.md:475`, `proposals/01-recovery-test-first.md:478`-`proposals/01-recovery-test-first.md:481` | A1 (`proposals/01-recovery-test-first.md:1121`) |
| SS4 | LOW | Cluster-lane cadence is now resolved as PR-gated for cluster-runtime Phase 6 slices plus nightly aggregate, with unrelated slices using scheduled/manual runs. Resolves prior-round MEDIUM open question 5. | `proposals/01-recovery-test-first.md:530`-`proposals/01-recovery-test-first.md:553`, `proposals/01-recovery-test-first.md:1146`-`proposals/01-recovery-test-first.md:1149`, `proposals/01-recovery-test-first.md:1204`-`proposals/01-recovery-test-first.md:1208` | A5 (`proposals/01-recovery-test-first.md:1125`) |
| SS5 | LOW | Adjacent public/user-reachable paths are confined to the Buildkite pipeline surface and local-channel GitOps; runtime services are explicitly internal-only. Anti-scope blocks Discord-visible writes, guild mutations, and remote apply. | `proposals/01-recovery-test-first.md:18`-`proposals/01-recovery-test-first.md:23`, `proposals/01-recovery-test-first.md:1105`-`proposals/01-recovery-test-first.md:1108` | — |
| SS6 | LOW | Deployment mode (local k3d + plan-only remote, per established Phase 5 posture) is preserved. "Existing remote plan-only lanes, if any, are unchanged; this recovery does not add or remove them." Resolves prior-round LOW finding 4. | `proposals/01-recovery-test-first.md:18`-`proposals/01-recovery-test-first.md:19`, `proposals/01-recovery-test-first.md:81`, `proposals/01-recovery-test-first.md:1075`-`proposals/01-recovery-test-first.md:1076`, `proposals/01-recovery-test-first.md:1105` | A7 (`proposals/01-recovery-test-first.md:1127`) |
| SS7 | LOW | Crossplane RCA failure correctly routes to research re-entry, not silent code change. Step 6b reachability tests must pass before Step 6c minimal NetworkPolicy adjustment; A1 invalidating signal stops the slice. | `proposals/01-recovery-test-first.md:469`-`proposals/01-recovery-test-first.md:485`, `proposals/01-recovery-test-first.md:1166`-`proposals/01-recovery-test-first.md:1169` | A1 (`proposals/01-recovery-test-first.md:1121`) |
| SS8 | LOW | Cluster-equipped lane availability failure has documented blocking-signal escalation (returns to supported-surface/deployment research instead of treating absence as residual). The lane existence itself is mandatory; only bounded validator paths may carry residual. | `proposals/01-recovery-test-first.md:530`-`proposals/01-recovery-test-first.md:553`, `proposals/01-recovery-test-first.md:1125`, `proposals/01-recovery-test-first.md:1204`-`proposals/01-recovery-test-first.md:1208` | A5 (`proposals/01-recovery-test-first.md:1125`) |
| SS9 | LOW | Observability of recovery progress is adequate. Each slice emits red-phase report, green-phase report, Step 6b output index, Step 6c consumption log, process-tree audit, and coverage-auditor before/after where classification changes; aggregate run emits E2E artifacts and `docs/infra-e2e-status.md`; SLICE-R.24 adds Buildkite verdict-grep output and exit code. | `proposals/01-recovery-test-first.md:1088`-`proposals/01-recovery-test-first.md:1093`, `proposals/01-recovery-test-first.md:1179`-`proposals/01-recovery-test-first.md:1194` | A6 (`proposals/01-recovery-test-first.md:1126`) |
| SS10 | LOW (watch) | A4's CI promotion of `services/api/tests/**` may expose testcontainers fixture brittleness if the Buildkite agent template lacks Docker. SLICE-R.02 acceptance now requires "Buildkite pre-flight verifies Docker availability for testcontainers Postgres before the API suite is counted as CI-gated; missing Docker is BLOCKED, not green" — A4 fallback prevents silent green. | `proposals/01-recovery-test-first.md:505`-`proposals/01-recovery-test-first.md:508` | A4 (`proposals/01-recovery-test-first.md:1124`) |
| SS11 | ACCEPT | Net-value statement is explicit, bounded, and matches the supported surface; negative-value trigger is named as return-to-Phase-2.5 condition, not a residual. | `proposals/01-recovery-test-first.md:1095`-`proposals/01-recovery-test-first.md:1100` | — |
| SS12 | ACCEPT | Migration in-place per slice and rollback by `git revert` per slice are clearly stated, with explicit decoupling: "CI lane changes can be reverted independently from product-code changes". | `proposals/01-recovery-test-first.md:1078`-`proposals/01-recovery-test-first.md:1086` | — |

## Adjacent public/user-reachable paths

None at runtime. The recovery's blast radius is:

- `.buildkite/pipeline.yml`, `.buildkite/e2e-fullstack.yml`,
  `.buildkite/pipeline-cluster.yml` (or equivalent), and
  `.buildkite/pipeline-nightly.yml` (or equivalent scheduled trigger) — CI
  configuration; visible to engineers, not users.
- `infra/tests/**`, `infra/tests/e2e/**` — test/validator surface; not
  user-reachable.
- `services/{api,discord,web}/tests/**` — test surface; not user-reachable.
- `gitops/channels/local/observability/networkpolicies/...` — local-channel
  only, touched by SLICE-R.01 and analogous policy paths in `cnpg-system` /
  `cert-manager`.
- Workflow artifacts under `research/`, `plans/`, `risk/` — process artifacts.

The web service (`services/web/`) is touched at the test level only
(SLICE-R.22) — runtime web behavior changes only as a consequence of
DECOMPOSE-rebuilt tests catching real behavior bugs, capped to ≤200 lines /
≤5 files per Step 6c diff. No user-visible mutation, no Discord guild mutation
(excluded by anti-scope, `proposals/01-recovery-test-first.md:1107`), no
production write.

The Crossplane / CNPG / cert-manager NetworkPolicy edits in SLICE-R.01 are
local-channel only — the policy file paths scope changes to the
`humility-local` cluster's GitOps tree.

## Convergence statement

This proposal is the right shape for Phase 4 supported-surface review:

1. **Termination signals do not fire (orthogonal, evaluated first and in
   order).** A1 invalidation is bounded to SLICE-R.01 with explicit
   RCA-re-entry; A2/A7/A8 have explicit research-re-entry consequences; the
   local-k3d proof target is real and the recovery's value is observable on it
   without real Vultr deployment.

2. **The LOW/MEDIUM/HIGH verdict is LOW.** All prior-round MEDIUM findings have
   been bound in the revised proposal:
   - CNPG / cert-manager adjacent operator-webhook namespaces are now bound
     into SLICE-R.01 contract (`proposals/01-recovery-test-first.md:466`-`proposals/01-recovery-test-first.md:467`,
     `proposals/01-recovery-test-first.md:478`-`proposals/01-recovery-test-first.md:481`).
   - Cluster-lane cadence is now resolved as PR-gated for cluster-runtime Phase 6
     slices plus nightly aggregate (`proposals/01-recovery-test-first.md:1146`-`proposals/01-recovery-test-first.md:1149`).
   - Plan-only remote lane preservation is now explicit
     (`proposals/01-recovery-test-first.md:1075`-`proposals/01-recovery-test-first.md:1076`).

3. **Net value clearly reduces a concrete current-state risk on the local k3d
   surface, AND that reduction outweighs the added blast radius (CI lane
   changes, validator churn) plus the migration cost (in-place, mostly
   reversible) plus the rollback path (per-slice git revert).** Risk reduced
   (false confidence from CAPTURED tests, Crossplane bring-up blocked, 31% DEAD,
   broken Phase 6 firstness across 19 INITs, security/policy literal mirrors)
   is materially larger than the bounded internal blast radius of CI churn and
   validator rewrites.

4. **Supported-surface posture preserved.** Local k3d for runtime proof; plan-
   only remote lanes unchanged; real Vultr apply remains anti-scope; no
   user-visible runtime mutation; no Discord guild mutation.

5. **Observability of recovery progress is adequate.** Per-slice
   red-phase-gate + green-phase-gate verdicts + coverage-auditor before/after +
   process-tree-auditor + Buildkite blocking verdict-grep wrapper (SLICE-R.24)
   together close the silent-success failure mode this recovery is fixing.

6. **Convergence with the other three Phase 4 risk reports** — audit (MEDIUM,
   PARTIAL/MISSING items now resolved by R1 binding into SLICE-R.03/R.24/R.25),
   scope (LOW), shortcut (MEDIUM, S1 now resolved by SLICE-R.24 blocking-wrapper
   R1 revision) — converges on a path forward. R1 revisions to the proposal
   address all named gaps.

The proposal advances on the supported-surface dimension without revisions.
Hand off to Phase 5 hookpoint research.

Verdict: LOW. TerminationSignal: NONE.
