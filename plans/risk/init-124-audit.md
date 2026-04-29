READ:
- proposals/05-synthetic-member-guard.md
- research/08-synthetic-member-guard-problem-map.md
- .tmp/rca/synthetic-public-member-pollution-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md

## Inputs read

- Proposal: `proposals/05-synthetic-member-guard.md`
- Problem map: `research/08-synthetic-member-guard-problem-map.md`
- RCA: `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`

## Checklist results

| Item | Status | Citation | Audit finding |
|---|---|---|---|
| 1. Net-value statement | PRESENT | `proposals/05-synthetic-member-guard.md:37-41`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` | The proposal states positive net value, names the concrete write-boundary contamination risk, cites the RCA's no-global-member-count finding and indirect roster risk, and explains why the smaller write-boundary slice outweighs read-side cleanup/migration burden. |
| 2. Scope + Anti-scope | PRESENT | `proposals/05-synthetic-member-guard.md:43-61`; proposal sufficiency rule at `/home/nes/ai/workflows/implementation-pipeline.md:86-87` | Scope covers the shared helper, service-layer guards, typed 422 errors, exact-read preservation, public-submit preservation, test intent, and residual-risk recording. Anti-scope explicitly excludes schema migration, `members.kind`, read-side roster hardening, SQL helper expansion, OAuth linking/conversion, data sweep/deletion, and Discord-visible action. |
| 3. Supported-surface track | PRESENT | `proposals/05-synthetic-member-guard.md:209-248`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` | The track covers deployment mode (`211-215`), cohort (`217-221`), adjacent paths (`223-229`), blast radius (`231-236`), migration/rollback (`238-242`), and observability (`244-248`). It also preserves the supported public submit path and names unchanged exact reads/pre-existing polluted rows as blast-radius notes. |
| 4. Assumption register | PRESENT | `proposals/05-synthetic-member-guard.md:250-254`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:91` | A1 through A3 each include evidence and an invalidation condition. A1 covers the `public:` discriminator with Discord snowflake and local helper evidence; A2 covers uniqueness of the synthetic write source with repository search evidence; A3 covers pre-INIT-120 roster chronology and identifies falsification by finding contrary pre-existing synthetic roster data. A3 is less procedural than A1/A2, but still present for audit purposes. |
| 5. Test-intent track | PRESENT | `proposals/05-synthetic-member-guard.md:256-310`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:92` | Each test group names the risk, intended behavior, selected level (`unit` + `component`), fixture source/application point, assumption links, observable signal, and residual risk. The track covers authenticated applicant rejection, public-submit preservation, owner assignment/claim, trust signal/compute/recompute, leadership alias expansion, roster entry creation, and member status mutation. |
| 6. Contract specifics: helper signature, exact boundaries | PRESENT | Helper: `proposals/05-synthetic-member-guard.md:69-79`, `proposals/05-synthetic-member-guard.md:108-136`; boundaries: `proposals/05-synthetic-member-guard.md:140-201` | The helper signature, prefix constant, input semantics, typed exception shape, endpoint mapping, and "raise immediately" rule are concrete. The proposal names exact guard call sites and expected API codes/bodies for authenticated application submit, claim/reassign/reactivate owner, trust signal/compute/recompute, leadership direct reject vs succession omit policy, roster entry creation, and member status mutation. |
| 7. Residual-risk artifact path named | PRESENT | `proposals/05-synthetic-member-guard.md:51`, `proposals/05-synthetic-member-guard.md:312-315`; Step 6b residual rule at `/home/nes/ai/workflows/implementation-pipeline.md:163-167` | The proposal names `plans/risk/init-124-test-residuals.md` for residual test and data risks. The path follows this repo's `plans/risk/` artifact convention used by the requested Phase 4 output. |
| 8. Out-of-scope follow-up | PRESENT | `proposals/05-synthetic-member-guard.md:334-337` | Follow-up is explicit: BL-008 / INIT-121-followup owns Discord OAuth linking, read-side roster hardening, and a `members.kind` schema column; a dedicated cleanup slice owns any synthetic rows already leaked into roster, trust, or owner fields. |

## Notable observations

- The proposal is audit-complete for Phase 3 presence obligations. I found no missing load-bearing checklist artifact.
- The design matches the approved problem map's risk shape: current risk is mostly exact UUID validation and unconstrained `roster_entries.member_id`, not a production global member-list query (`research/08-synthetic-member-guard-problem-map.md:129-132`; `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:9-15`).
- The public-intake exception is explicitly protected in both design and tests: public submit must keep creating/reusing synthetic members while non-public write surfaces reject them (`proposals/05-synthetic-member-guard.md:34-35`, `proposals/05-synthetic-member-guard.md:264-268`).
- Low residual audit note: A3's invalidation condition is adequate for Phase 4 presence, but Phase 5/6 should make the concrete database check explicit if any implementation step depends on distinguishing historical roster pollution from new-write prevention.

## Verdict

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
