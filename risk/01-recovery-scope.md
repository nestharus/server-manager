Verdict: LOW

# Scope risk — recovery test-first proposal (`proposals/01-recovery-test-first.md`)

Date: 2026-04-27
Assessor: scope risk reviewer (Phase 4 risk gate, post-revision)

## Convergence statement

The proposal converges with declared scope ("test-first recovery of
INIT-100..119") on every named risk vector. The scope summary
(lines 3-16), explicit non-goals (lines 18-23), aggregate anti-scope
(lines 1102-1115), and per-slice anti-scope clauses uniformly reject
new product features, INIT-120+ surfaces, real Vultr apply, and
aesthetic rewrites of working implementation. Each of the 25 slices
maps to one of: a single live-bug repair (R.01), CI wiring of
already-existing tests (R.02, R.03, R.24), test rewrites against
captured/HARMFUL self-referential assertions (R.04), per-layer Phase 6
re-evidencing (R.05-R.21), DECOMPOSE rebuilds with a structural diff
cap (R.18, R.19, R.20, R.22, R.23), or legacy-test classification with
a four-way disposition (R.25).

The prior scope review's only substantive caveat — that DECOMPOSE
slices had a process-rule rather than a structural-lock guard against
implicit rewrite — is now addressed in the proposal text itself:
SLICE-R.18, R.19, R.20, R.22, and R.23 each cap the Step 6c
product-code diff at 200 changed lines / 5 files, with the
process-tree-auditor verifying the bound and any excess escalating to
a separate proposal (lines 822-825, 844-847, 865-868, 908-911,
935-938; tracked in the "Resolved Phase 4 risk gate decisions" block
at lines 1142-1145 and Acceptance summary at lines 1212-1215). With
that lock in place, the residual scope risk is process discipline at
two specific boundaries (B4, B5 below), neither of which rises above
LOW. Verdict therefore LOW.

## Boundary findings

### B1 — Recovery scope vs new product features (LOW)

Lines 18-23 declare the proposal does not add product features,
deploy to real Vultr, start INIT-120+, or rewrite working
implementation for aesthetic reasons. Anti-scope (lines 1104-1115)
repeats this operationally and adds "Discord-visible writes or guild
mutations" and "New hosting decisions". Each slice has its own
anti-scope clause bound to its concern: R.01 line 489-490 forbids
operator upgrades and broad security redesign; R.02 line 521-522
forbids API behavior rewrites and new Discord/UI features;
R.10 line 688 forbids Crossplane composition redesign; R.14 line 753
forbids auth/rate-limiting/Kong Manager additions; R.22 line 914
forbids INIT-120+ product UI surfaces; R.25 line 1002-1003 forbids
new daemon feature work. No slice contract introduces a new product
surface, new hosting decision, or new INIT layer. Convergent.

### B2 — Aesthetic rewrites of working implementation (LOW)

Lines 18-19 disclaim aesthetic rewrites. Anti-scope line 1111-1112
names "Re-authoring working implementation where independent tests
already verify the intended contract". CONTINUE slices R.05-R.17
qualify the code agent as "code agent if needed" (e.g. lines 588,
607-608, 625, 643-644, 660-661, 675-676, 692-693, 708-709, 724-725,
741-742, 757-758, 774-775, 791-792). SLICE-R.04 (line 559-583)
rewrites *tests*, not product code: owner-agent line 562-563 binds
the code agent to "removal of harmful or invalid tests" only;
anti-scope line 582-583 forbids "product implementation fixes except
deleting or replacing invalid tests". Convergent.

### B3 — DECOMPOSE preservation of implementation contract (LOW)

DECOMPOSE slices are R.18 (auth), R.19 (policy), R.20 (tenant), R.22
(web), and R.23 (E2E). Each derives the contract from proposal text,
not current implementation (R.18 line 814-816, R.19 line 837-839,
R.20 line 858-859, R.22 line 898-900, R.23 line 923-925). The
implementation-survives-only-if-tests-pass discipline is repeated per
slice (R.18 line 820-821, R.19 line 843, R.20 line 863-864, R.22
line 907). Crucially, all five slices now carry an identical
structural lock on Step 6c product-code diffs:

- R.18 line 822-825
- R.19 line 844-847
- R.20 line 865-868
- R.22 line 908-911
- R.23 line 935-938

The lock reads "Step 6c product-code diff is structurally locked to
at most 200 changed lines and at most 5 files; process-tree-auditor
verifies the bound, and any excess escalates to a separate proposal.
Addresses SCOPE-B3." This converts the prior process-rule guard into
a verifiable structural cap with explicit escalation. Assumption A3
(line 1123) names the residual: if independent tests prove the
implementation fundamentally wrong beyond minor 6c repair, the slice
splits or returns to Phase 4 rather than absorbing a silent rewrite.
The structural lock makes that escalation visible at the
process-tree-audit boundary. Convergent. The prior B3 caveat is
resolved.

### B4 — Legacy root-daemon test handling (LOW with watch signal)

The user's framing is "modernize / migrate vs rewrite to current
behavior". SLICE-R.25 (lines 975-1003) is dedicated to this and
classifies every legacy test file in repo-root `tests/`,
`services/api/tests/`, and `services/discord/tests/` into exactly one
of four buckets: `KEEP_AS_IS`, `MODERNIZE`, `MIGRATE`, or
`DELETE_AND_REWRITE` (lines 988-997). Three of four buckets are
clearly modernize/migrate-shaped. `DELETE_AND_REWRITE` is the only
rewrite path, and it is gated: "DELETE_AND_REWRITE files are removed
only after replacement tests or residual-risk disposition exists"
(line 996-997). Owner-agent line 977-979 binds replacement-test
authorship to behavior-investigator (legacy intent), test-writer, and
code agent for "migration/deletion mechanics" only. The audit
disposition row at line 114 reinforces that legacy tests are still
"not treated as product-service proof without modernization", and
anti-scope line 1002-1003 forbids "treating legacy root tests as
service proof before classification".

Watch signal: SLICE-R.25 does not explicitly repeat the SLICE-R.04
discipline that rewritten tests must derive from "original proposals,
commits, and product goals, not from current resolver output"
(R.04 line 565-567). The general A2 invariant (line 1122) and the
behavior-investigator owner-agent role imply contract-derived
authorship, but a future agent reading R.25 in isolation could
plausibly read DELETE_AND_REWRITE as "rewrite from current
implementation behavior". Recommend the Phase 5 hookpoint handoff
for SLICE-R.25 (line 1172-1174) explicitly state that
DELETE_AND_REWRITE replacement tests are contract-derived, mirroring
SLICE-R.04. Not a scope blocker — the same discipline applies via
A2 — but worth pinning at hookpoint time so it cannot drift.

### B5 — Crossplane bug-fix slice narrowness (LOW with note)

SLICE-R.01 (lines 453-490) repairs operator-webhook reachability via
NetworkPolicy correction. The user's framing is "one NetworkPolicy
change". The proposal scope is broader: the contract covers
Crossplane, CNPG, cert-manager, "and any other namespace where the
same INIT-117 policy pattern was applied" (line 462-468). Step 6b
must prove reachability across all four namespace classes
(line 472-475); Step 6c "applies the minimal NetworkPolicy adjustment
needed in each affected operator-webhook namespace without
broadening unrelated namespace access" (line 479-481). Anti-scope
line 489-490 explicitly forbids "Crossplane/CNPG/cert-manager
upgrade, no provider replacement, no broad security-policy redesign,
no real Vultr deployment".

Note: this is broader than "one NetworkPolicy change" but the
broadening tracks one root-cause pattern (the INIT-117 empty-selector
allow-only-observability NetworkPolicy applied to multiple operator
namespaces), not a cluster-security rework. The "minimal adjustment
per affected namespace" clause and the per-namespace anti-scope keep
it pattern-bounded. Cross-reference: R.21 line 885-886 ("The
Crossplane webhook NetworkPolicy regression is guarded by SLICE-R.01
tests before observability policy changes are accepted") prevents
R.21 (observability) from re-broadening the fix. R.11 line 701-702
adds the same guard from the cluster-security side. Convergent. Note
the multi-namespace scope to Phase 5 hookpoint research so the
"any other namespace" clause is enumerated, not discovered ad hoc at
6c time.

### B6 — CI lane wiring vs new test authorship (LOW)

SLICE-R.02 owner-agent line 494-496 binds test-writer to "only if CI
contract tests are missing"; the slice promotes existing
DEAD/VERIFIED API tests to operational status (line 503-504) without
authoring new ones, and CAPTURED Discord tests are explicitly not
promoted to VERIFIED merely because they run (line 509-510). The
HARMFUL Buildkite step-list assertion is forwarded to SLICE-R.04 for
rewrite ownership (line 514-515), not authored fresh in R.02.

SLICE-R.03 (lines 524-557) lifts existing runtime validators (named
at line 538-542) to a cluster-equipped lane; it does not author new
validators. Coverage-auditor line 552-553 records DEAD-to-VERIFIED
transitions for existing files.

SLICE-R.24 (lines 943-973) wraps existing red/green/process-tree
report formats in Buildkite verdict-grep gates; it does not author
new gate types or new tests. Anti-scope line 973: "no replacement of
the formal Phase 4/6 model gates."

SLICE-R.25 (lines 975-1003) classifies and modernizes existing
legacy tests; new test authorship within R.25 is bounded to the
DELETE_AND_REWRITE replacement path (gated by B4). Owner-agent
line 977-979 binds the code agent to "migration/deletion mechanics
only". Convergent.

### B7 — INIT-119 E2E rebuild preserves architecture (LOW)

SLICE-R.23 (lines 916-941) is the slice the user is most directly
concerned about. Contract line 923-925: "rebuild the 19 cross-cutting
tests from per-layer contracts while preserving `run-fullstack.sh`,
`infra/tests/e2e/lib/`, Playwright harness, and Buildkite pipeline
architecture." Acceptance line 927-928: "The 19 test files are not
copied from the WIP same-run suite as canonical contract; they are
regenerated from per-layer contracts." Fixture source line 939:
`infra/tests/e2e/lib/`, Playwright fixtures, per-layer contract
fixtures — i.e. the harness becomes a fixture, not a rewrite target.
Step 6c product-code diff is additionally locked at 200 lines / 5
files (line 935-938), which would catch any silent harness rewrite
attempted under the test-rebuild banner.

Assumption A8 (line 1128) names the only path that voids harness
preservation: hookpoint research finds harness encodes broken WIP
assumptions, in which case the affected harness component is
decomposed further. The architecture is preserved by default;
replacement only occurs on documented cause and only via further
decomposition. Phase 5 hookpoint handoff line 1175-1177 explicitly
enumerates the surviving framework files. Convergent.

## Residual scope concerns

- **B4 watch signal**: SLICE-R.25 DELETE_AND_REWRITE does not repeat
  SLICE-R.04's contract-derived authorship discipline. Recommend the
  Phase 5 hookpoint handoff for R.25 (line 1172-1174) make this
  explicit. Not a blocker; A2 covers it at the assumption-register
  level.

- **B5 enumeration**: SLICE-R.01's "any other namespace where the
  same INIT-117 policy pattern was applied" clause (line 467) needs
  Phase 5 hookpoint enumeration so the affected namespace set is
  fixed before Step 6b, not discovered at Step 6c time. Hookpoint
  line 1166-1169 already names this; recommend the hookpoint output
  produce a closed list rather than an "and similar" clause.

- **HARMFUL-test cross-slice ownership**: R.02 line 514-515 forwards
  the HARMFUL Buildkite step-list assertion rewrite to R.04, while
  R.04 line 571-572 owns the rewrite. Slice ordering is unambiguous
  (R.04 follows R.02 in numbering, and R.02 acceptance allows the
  HARMFUL to be "removed or rewritten as behavioral pipeline
  validation within SLICE-R.04"). Flag for Phase 5 hookpoint to
  confirm slice ordering does not regress; this is administrative,
  not scope-shaped.

## Summary

The proposal stays inside declared recovery scope on every named
risk. The Crossplane fix is bound to one NetworkPolicy pattern across
a closed list of operator namespaces (B5), CI slices (R.02, R.03,
R.24, R.25) wire and classify existing tests rather than author new
ones (B6), the E2E rebuild preserves the harness architecture and
re-derives only test bodies (B7), legacy root daemon tests are
classified into modernize/migrate-shaped buckets with the one
rewrite path gated by replacement-test or residual disposition (B4),
and the DECOMPOSE slices now carry a structural diff cap (200 lines
/ 5 files, process-tree-audited) that converts the prior B3
process-rule guard into a verifiable hard limit (B3).

Verdict LOW. The two watch signals (B4 contract-derivation at R.25
hookpoint; B5 closed-list namespace enumeration at R.01 hookpoint)
are administrative tightening for Phase 5, not scope blockers.
