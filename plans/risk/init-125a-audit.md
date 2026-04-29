READ:
- proposals/06-members-kind.md
- research/10-members-kind-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md

## Inputs read

- Proposal: `proposals/06-members-kind.md`
- Problem map: `research/10-members-kind-problem-map.md`
- RCA: `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`

## Checklist results

| Item | Status | Citation | Audit finding |
|---|---|---|---|
| 1. Net-value statement | PRESENT | `proposals/06-members-kind.md:31-33`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` | The proposal states positive net value, names the current brittle `public:` prefix identity rule, and explains that the schema discriminator reduces INIT-124's deferred debt while preserving existing guard behavior. |
| 2. Scope + Anti-scope | PRESENT | `proposals/06-members-kind.md:35-55`; proposal sufficiency rule at `/home/nes/ai/workflows/implementation-pipeline.md:86-87` | Scope covers the migration, backfill, read/insert/mapping contract, kind-based helper, guard call-site updates, public-intake/default real-member stamping, fixtures, and tests. Anti-scope explicitly excludes OAuth, conversion/link tables, read-side cleanup, `linked_pending`, caller-supplied `kind`, error-code renames, and Discord-visible mutation. |
| 3. Supported-surface track | PRESENT | `proposals/06-members-kind.md:206-245`; pipeline supported-surface requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` and audit role at `/home/nes/ai/workflows/implementation-pipeline.md:100-104` | The proposal covers deployment mode (`208-210`), cohort (`212-215`), adjacent paths (`217-221`), blast-radius notes (`223-228`), migration/rollback (`230-233`), and observability (`235-245`). It is grounded in the problem map's current supported paths and blast radius (`research/10-members-kind-problem-map.md:34-67`). |
| 4. Assumption register | PRESENT | `proposals/06-members-kind.md:247-251`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:91` | A1 through A3 each include evidence and an invalidation condition. A1 covers existing row classification, A2 covers insert-path ownership, and A3 covers the public `MemberRead` contract and exposure risk. |
| 5. Test-intent track per `impl-pipeline.md:92` | PRESENT | `proposals/06-members-kind.md:253-260`; required fields at `/home/nes/ai/workflows/implementation-pipeline.md:92`; Step 6 preservation rules at `/home/nes/ai/workflows/implementation-pipeline.md:146-167` | Every listed test group has the required fields: risk, acceptance/behavior, selected level, fixture source or application point, assumption link, observable signal, and residual risk. The track covers migration, helper behavior, public-intake creation, normal creation, INIT-124 boundary guards, and INIT-120 public submit. |
| 6. Migration concrete: column add, backfill, NOT NULL, CHECK | PRESENT | Scope summary at `proposals/06-members-kind.md:37-39`; concrete migration body at `proposals/06-members-kind.md:108-129`; detailed upgrade at `proposals/06-members-kind.md:268-274`; problem-map migration pattern at `research/10-members-kind-problem-map.md:69-73` | The migration is concrete: add nullable `members.kind`, backfill `public:%` rows to `public_intake` and others to `discord`, clear default, alter to `NOT NULL`, and add `members_kind_valid`. The downgrade drops the check constraint and column (`proposals/06-members-kind.md:132-137`, `proposals/06-members-kind.md:276-282`). The create/drop name pairing matches the repo naming convention that prefixes check constraints as `ck_<table>__<constraint>` (`services/api/app/repositories/db.py:14-21`, `migrations/versions/wu-003b_audit_context_columns.py:45-57`). |
| 7. Residual-risk artifact path named | PRESENT | `proposals/06-members-kind.md:262-264`; Step 6b residual-output rule at `/home/nes/ai/workflows/implementation-pipeline.md:163-167` | The proposal names `plans/risk/init-125a-test-residuals.md`. The pipeline's generic residual path is `risk/NN-test-residuals.md`; this repo's active requested artifact convention is `plans/risk/`, so the named path is sufficient if Phase 6 uses it consistently in the output index and residual links. |
| 8. Out-of-scope follow-up | PRESENT | `proposals/06-members-kind.md:284-288`; RCA decomposition at `.tmp/rca/discord-oauth-linking-FINDINGS.md:229-259` | Follow-up ownership is explicit: BL-016 owns Authentik Discord OAuth, BL-017 owns conversion/link records/application re-pointing, and BL-018 owns historical roster/trust cleanup and read hardening. This matches the RCA's finding that `members.kind` is the right first discriminator slice but not the full linking fix. |

## Notable observations

- The proposal is audit-complete for Phase 3 presence obligations. I found no missing load-bearing checklist artifact.
- The proposal resolves the RCA's open `linked_pending` issue by anti-scoping it and narrowing `kind` to `discord` plus `public_intake` (`proposals/06-members-kind.md:49-52`; `.tmp/rca/discord-oauth-linking-FINDINGS.md:256-259`).
- The migration downgrade sketch is concrete and convention-compatible, but Phase 5/6 should preserve the constraint-name convention exactly because Alembic `create_check_constraint("members_kind_valid", ...)` will be materialized under the metadata naming convention as `ck_members__members_kind_valid`.
- No supported-surface termination trigger is apparent from the audit checklist. The current-state risk is documented as magic-prefix identity and test reliance on prefix semantics (`research/10-members-kind-problem-map.md:42-48`), while the RCA says this discriminator reduces that risk without pretending to solve identity linking (`.tmp/rca/discord-oauth-linking-FINDINGS.md:149-165`, `.tmp/rca/discord-oauth-linking-FINDINGS.md:229-259`).

## Verdict

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
