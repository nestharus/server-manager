# AI — Coverage Risk Assessment

**Rating: LOW**

The AI roadmap decomposes every engineering item into work units. All 13 Phase 0 deliverables and all 18 value slices (VS-001…VS-018) map to at least one work unit with concrete contracts and binary acceptance criteria. No orphan work units. A small number of minor phrasing and AC-completeness observations are recorded below as INFO/LOW; none blocks the LOW rating.

## Findings

### F-1. Every engineering item is decomposed

**Severity: NONE**

Cross-reference of `engineering roadmap.md` items to `ai roadmap.md` work units:

**Phase 0 deliverables (13):**
- Persistence substrate with migrations → WU-001
- Single write-path mutation primitive → WU-002
- Audit and notification event contract → WU-003, WU-003B
- Authority grant foundation → WU-004
- Permission intent foundation → WU-006A, WU-006B (drift)
- Chapter role and roster entry foundation → WU-007B, WU-007C (plus WU-007A chapter template)
- Policy version framework → WU-005
- Scheduler → WU-008A
- Discord interaction framework → WU-009C, WU-009D
- Graceful degradation mechanics → WU-008B
- Data portability as a schema design property → embedded AC on WU-003B, WU-004, WU-005, WU-006A, WU-006B, WU-007A, WU-007B, WU-007C
- Shared test harness → WU-009A, WU-009B
- Deployable service substrate aligned to `infra/` → WU-010A, WU-010B, WU-010C, WU-010D, WU-010E

**Phase 0 acceptance criteria:**
- Scheduler technology selected → WU-008A (selection happens in its `Deep` proposal)
- `mutate_entity()` primitive → WU-002
- Audit action/target registry → WU-003
- Correlation/causation propagation at request boundary → WU-003 (+ WU-016B Discord-side adapter)
- Monorepo test harness + fixtures → WU-009A, WU-009B
- Deployable substrate → WU-010C/D/E
- Secret management → WU-010A, WU-010B (fail-fast on missing required secrets)
- Authority/intent/policy/chapter-role/roster foundations → WU-004, WU-006A, WU-005, WU-007B, WU-007C
- Discord interaction framework capability → WU-009C, WU-009D
- Graceful degradation mechanics → WU-008B
- Data portability schema property → covered per-aggregate (see above)

**Phase 1–4 value slices (18):**

| Engineering slice | AI work units |
|---|---|
| VS-001 | WU-011, WU-012, WU-013 |
| VS-002 | WU-014, WU-015A, WU-015B |
| VS-003 | WU-016A, WU-016B |
| VS-004 | WU-017 |
| VS-005 | WU-018, WU-019, WU-020 |
| VS-006 | WU-021, WU-022, WU-023a, WU-023b |
| VS-007 | WU-024, WU-025A-create, WU-025A-events, WU-025B, WU-025C, WU-026 |
| VS-008 | WU-027, WU-028A, WU-028B-api, WU-028B-discord |
| VS-009 | WU-029A, WU-029B-materialize, WU-029B-deliver, WU-029C |
| VS-010 | WU-030A, WU-030B |
| VS-011 | WU-033, WU-034 |
| VS-012 | WU-035, WU-036a, WU-036b |
| VS-013 | WU-037 |
| VS-014 | WU-038A, WU-038B |
| VS-015 | WU-031, WU-032 |
| VS-016 | WU-039, WU-040A, WU-040B-extract, WU-040B-correct, WU-041A, WU-041B |
| VS-017 | WU-042, WU-043A, WU-043B |
| VS-018 | WU-044A, WU-044B, WU-045A-applications, WU-045A-tickets, WU-045B |

No engineering item is partially decomposed. No orphan work units.

**Recommendation:** No action required.

---

### F-2. Hosting-decision deliverable is a phase gate, not a work unit

**Severity: INFO**

Engineering roadmap Phase 0 AC: "Hosting decision is formalized in `DECISIONS.md`." The AI roadmap encodes this at Phase 0's opening line as a phase-boundary gate ("Phase 0 does not close until `DECISIONS.md` records the hosting decision"), not as a WU with acceptance criteria. This is structurally appropriate — a decision-artifact is not a test/code unit — and does not constitute uncovered scope.

**Recommendation:** No action required.

---

### F-3. WU-008B does not surface "retries" in its acceptance criteria

**Severity: LOW**

Engineering roadmap Phase 0 AC: "Graceful degradation mechanics are selected for deferred effects, retries, and recovery validation." WU-008B has ACs for precondition validation (`precondition_status`), deferred-effect queryability, and degraded-state summary, but no explicit retry-semantics AC. Retry mechanics will presumably fall out of WU-008B's `Deep` proposal, but the roadmap does not commit to an observable retry criterion.

**Recommendation:** Optional — add a fourth AC to WU-008B specifying retry observability (e.g., "A deferred effect that fails a consequential precondition is eligible for retry after operator resolution and retry state is inspectable via the degraded-state summary"). Low urgency because selection happens at proposal stage.

---

### F-4. Audit-entry data portability AC is not explicitly stated on WU-003

**Severity: LOW**

WU-004/005/006A/006B/007A/007B/007C each carry a "round-trip to a documented JSON export shape" AC, satisfying the Phase 0 "data portability as a schema design property" deliverable for those aggregates. WU-003 (audit registry) and WU-003B (notification events) handle portability asymmetrically: WU-003B declares "serialize to a documented JSON envelope that downstream workers can replay or export," but WU-003 contains no export-shape AC for audit entries, despite the engineering roadmap naming "Audit and notification event contract" as a single Phase 0 deliverable.

**Recommendation:** Add an AC on WU-003: "Audit entries round-trip to a documented JSON export shape that preserves correlation/causation identity and actor attribution."

---

### F-5. A few acceptance criteria use soft phrasing that narrows testability

**Severity: LOW**

Most ACs are crisp and binary (HTTP status codes, exact enum values, version increments, 412 responses, exactly-once behaviors). A handful use slightly subjective phrasing:

- WU-016A: "Scoped audit queries **reuse the authority guard rather than duplicating permission checks**." Intent is clear, but "reuse rather than duplicate" is a structural property, not a behavioral assertion. Testable via a 403 behavioral test on scoped queries.
- WU-030A: "Signal writes **remain append-safe under the audit chain and do not bypass** the policy version substrate." Can be verified by checking the audit chain and policy-version reference, but the phrasing invites interpretation.
- WU-010A/B: "Settings contracts expose a documented source map so deploy-time configuration is **inspectable without reading implementation code**." Testable by asserting `SettingsSourceRead` exists with declared fields, but the "inspectable" word is soft.
- WU-032/WU-045B: "Surfaced as stale ... signal **rather than silent empty results**." Testable only if the contract declares a specific field for the stale-signal; the contracts do include such fields (`stale_projections`, `flagged_items`), so this is verifiable.

None of these are unverifiable — each can be operationalized as a test — but a future risk-agent pass would benefit from sharper wording.

**Recommendation:** Optional — rewrite the flagged ACs to name the specific observable: the HTTP status/field/enum the test will assert on.

---

### F-6. WU-041B references an evaluation result value (`auto_probation`) not in the WU-041A contract enum

**Severity: LOW**

WU-041A declares `ComplianceEvaluationRead.result in ["compliant", "violation", "insufficient_evidence"]`. WU-041B AC reads: "A `flag_for_review` or `auto_probation` result moves the roster entry to `under_review` through the roster API path." Neither `flag_for_review` nor `auto_probation` is a declared `result` value; they appear to be consequence-policy outcomes from `ComplianceRule.consequence_policy` rather than result values, but the AC wording conflates the two fields. This is a contract-consistency flag, not a missing work unit — tests written against WU-041B alone would not know which field to check.

**Recommendation:** Tighten WU-041B AC: name the field (`consequence_policy` outcome or `result`) and align the vocabulary with WU-039/WU-041A. If `flag_for_review`/`auto_probation` are consequence actions, WU-041A's contract should surface them on `consequence_applied`.

---

## Summary table

| ID | Finding | Severity |
|----|---------|----------|
| F-1 | Every engineering item is decomposed; no orphans | NONE |
| F-2 | Hosting decision encoded as phase gate, not WU | INFO |
| F-3 | WU-008B lacks explicit retries AC | LOW |
| F-4 | WU-003 lacks explicit audit JSON-export AC | LOW |
| F-5 | A few ACs use soft/structural phrasing | LOW |
| F-6 | WU-041B names result values absent from WU-041A enum | LOW |

## What LOW requires

- Every Phase 0 deliverable (13) and acceptance criterion has at least one WU or explicit phase gate — verified.
- Every value slice VS-001…VS-018 has one or more WUs whose contracts collectively cover submission, lifecycle, worker, and Discord adapter surface as described in the engineering roadmap — verified.
- No work unit in the AI roadmap lacks a parent initiative line — verified (spot-checked all 78 WUs).
- Acceptance criteria are predominantly binary (HTTP codes, enum values, version increments, 412/409 responses, exactly-once assertions) — verified; the soft-phrasing exceptions in F-5 remain testable.
- The dependency graph's topological sort covers all 78 WUs with no disconnected nodes — verified against the roadmap's own Phase-by-Phase cohort listing.

If any of the LOW findings (F-3, F-4, F-5, F-6) escalate — for example, if WU-008B's retry semantics remain unspecified through its proposal phase, or if F-6's contract inconsistency is not resolved at WU-041A/WU-041B implementation time — the rating would move to MEDIUM.
