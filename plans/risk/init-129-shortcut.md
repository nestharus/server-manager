# INIT-129 — Shortcut risk gate

**Verdict:** LOW

## Question: did this slice take a shortcut that defers risk?

### S1 — Do we still need the historical-row cleanup Job?

The original BL-018 plan said "one-shot cleanup Job that scans
`roster_entries`, `trust_profiles`, etc. for synthetic refs". This
slice does NOT add such a Job.

**Reason:** the cleanup-Job design was load-bearing only under the
abandoned member-link/conversion model (BL-017's original framing).
Post-INIT-128 there is no linking — synthetic rows are simply
historical inert data. The 18 humility-local rows are e2e fixture
artifacts, not user data; production hasn't shipped. The
defense-in-depth `is_synthetic_member()` guards already prevent any
read or write surface from treating them as real members.

If a future production cluster ever accumulates synthetic rows
(e.g., from re-importing historical e2e snapshots), a one-off SQL
`DELETE` is sufficient. There's no recurring cleanup need.

Not a shortcut. The risk shifted out from under the plan.

### S2 — `_insert_member` lost its `_kind` parameter

I changed the signature from
`_insert_member(..., _kind: str = "discord")`
to
`_insert_member(...)` (kind is hardcoded `'discord'` in SQL).

**Risk:** if a future slice needs to insert a non-discord member
through this helper, it has to be re-parameterized.

**Mitigation:** the test fixture
`SyntheticMemberGuardMemberFactory` does NOT use `_insert_member`;
it issues raw SQL directly. So tests can still inject synthetics
for guard verification. Production code has no reason to insert
non-discord rows post-INIT-128.

Not a shortcut. The hardcode reflects the actual product
constraint.

### S3 — Removed test coverage of `resolve_or_create_public_intake_member`

`tests/test_public_intake_synthetic_member.py` (183 lines, 7+ test
cases) is deleted whole.

**Risk:** loss of regression coverage if the synthetic-creation
helper resurfaces.

**Mitigation:** equivalent positive coverage of the now-only-path
is in `test_members.py::test_resolve_or_create_real_discord_member_*`
(3 tests including concurrency). Negative coverage of synthetic
rejection is in `test_applications.py::test_authenticated_submit_rejects_synthetic_applicant`,
`test_owner_transition_rejects_synthetic_new_owner`,
`test_claim_rejects_synthetic_owner_actor`,
`test_patch_member_status_rejects_synthetic_member` (4+ tests via
`SyntheticMemberGuardMemberFactory`). Discriminator coverage is in
`test_synthetic_member_helper.py` (6 parametrized cases) +
`test_members_kind_migration.py` (3 tests).

The deleted file's positive cases (creating + reusing synthetic
rows) are no longer needed because the only code that did that is
deleted.

Not a shortcut. Loss is proportional to the dead code removed.

## Verdict

LOW — no risk deferred. The cleanup-Job was a phantom requirement
under a superseded design; coverage loss matches dead code surface.
