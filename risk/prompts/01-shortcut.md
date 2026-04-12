# Risk assessment prompt — SHORTCUT risk for proposals/01-v1-scope.md

## Hard rules (read these first)

**YOU are the shortcut-risk assessor. YOU do the assessment
yourself. Do not launch, spawn, dispatch, or report on any other
agent.** There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/01-shortcut.md`.

- **DO** read `proposals/01-v1-scope.md` in full
- **DO** read `DECISIONS.md` (especially D1, D2, D3 which codify
  the "no SQLite, no shims, no jumping to solutions" rules),
  `AGENTS.md`, `NOTES.md`, the research docs, and **the pre-research
  code in `daemon/`, `forms/`, `docs/APPLICATIONS_SKETCH.md`, and
  `docs/DAEMON_DESIGN.md`** — you need to know whether the proposal
  is secretly carrying forward shortcuts from the pre-research draft
- **DO** write the assessment to `risk/01-shortcut.md` using your
  Write tool
- **DO NOT** modify any file other than `risk/01-shortcut.md`
- **DO NOT** rewrite the proposal
- **DO NOT** launch subprocesses
- **DO NOT** print progress to stdout

## What you're assessing

Your job is to identify **shortcut risk** — whether the proposal
itself introduces its own shortcuts.

The specific failure mode you're guarding against: "the proposal
fixes one shortcut (e.g., SQLite, dead bot dependency) by
introducing another shortcut (hardcoded values, duplicated logic,
symptom-masking workarounds, source-vs-artifact confusion,
compatibility shims)."

Check for each of these in `proposals/01-v1-scope.md`:

1. **Compatibility shims / feature flags for old behavior**: does
   the proposal introduce "for now" code paths, feature flags for
   "migrating," dual-write layers, or any other transitional
   complexity? `DECISIONS.md#D1` and the "no compat shims" rule in
   `AGENTS.md` forbid this. The proposal explicitly says it follows
   this rule — is it actually true?
2. **Hardcoded values that should be config**: are there magic
   numbers, channel/role IDs, thresholds, or policy decisions
   hardcoded in a way that makes future changes expensive? Or
   conversely, are there things made configurable that should be
   hardcoded?
3. **Duplicated logic**: does the proposal rebuild primitives that
   already exist in `discord.py`, or in the pre-research code the
   research told us to evaluate rather than discard? Is the claim
   helper, for example, rebuilding something that `discord.py` or
   a library already provides?
4. **Source-vs-artifact confusion**: forms are "YAML in repo,
   snapshotted to DB on publish." Is the SOURCE OF TRUTH clear at
   every point in the lifecycle? Can forms drift between YAML and
   DB snapshots silently? Can activity rules (which are DB-only)
   and forms (YAML-primary) produce operator confusion about
   "where do I edit this?"
5. **Symptom-masking workarounds**: the proposal has OCR confidence
   thresholds of 0.85 / 0.70. Are these numbers justified or just
   plausible-sounding defaults? Is the "flag for review" state
   being used as a catch-all for everything the pipeline can't
   handle, effectively masking the real problem?
6. **Test scope that hides real risk**: the proposal's testing
   strategy requires a staging Discord guild. If that turns out to
   be unavailable, does the proposal fall back to "we'll just test
   in production"? Is there any soft implication that testing can
   be deferred?
7. **Schema shortcuts**: JSONB columns are used for
   `settings_json`, `preprocessing_json`, `details_json`,
   `spec_json`, etc. Is each one actually structured data that
   would be better as explicit columns, being smuggled into JSONB
   because "we haven't figured it out yet"? That's a classic
   shortcut.
8. **"We'll add it later" as a deferral shortcut**: the anti-scope
   (§14) is long. Are any of those items actually required for v1
   to work, being deferred by asserting "out of scope" rather than
   confronting them? Example: moderation tooling is listed as
   out-of-scope because "no mods today," but the ticket subsystem
   includes a `moderator` ticket type that routes to an empty
   role. Is that half-solution creating a worse shortcut?
9. **Transactional shortcuts**: the proposal says "saga-style
   provisioning, not a fake global transaction." Is that actually
   correct, or is it a shortcut around not implementing proper
   compensation / rollback semantics? Read the rollback plan
   (§13) carefully — is "leave orphaned roles" a principled
   design or a cleanup-is-hard shortcut?
10. **Pre-research code carryover**: the proposal explicitly says
    it treats `daemon/` as a pre-research draft and may discard
    it. Is it actually carrying forward shapes from the draft
    that were wrong, like the split-flow modal design, or the
    SQLite schema structure in any form? Read
    `daemon/applications.py`, `daemon/db.py`, `daemon/claim.py`,
    `daemon/config.py`, and `daemon/__main__.py` and cross-check
    against the proposal to see if any questionable patterns got
    carried over.
11. **Operator convenience shortcuts**: CLI dry-run /
    execute flow for provisioning — is this a good pattern or a
    shortcut around "we couldn't figure out approval workflow"?
12. **OCR mixed-architecture complexity**: the proposal runs
    classical OCR primary + LLM fallback with cross-validation. Is
    this actually the right architecture, or is it a shortcut
    around committing to one path because neither was clearly
    good? The research recommended mixed; the proposal follows
    the recommendation. Is the complexity justified by real
    accuracy requirements, or is it defensive overengineering?
13. **Audit log duplication**: `audit_events` exists because
    Discord's 45-day retention is insufficient. Is the proposal
    duplicating something Discord already has, or is this really
    a necessary copy? Are the fields captured actually the fields
    needed, or is it "let's log everything" as a shortcut around
    knowing what matters?
14. **Supabase RLS handwave**: §9 says "RLS is not a meaningful
    control plane because the daemon is the only client." Is
    that actually true, or is it a shortcut around configuring
    RLS properly?
15. **Any other shortcut** — shortcut risk is pattern detection.
    Read the proposal with a suspicious eye and look for "this
    is suspiciously convenient," "why not just X," and "where's
    the actual design effort here."

## Output format

Write `risk/01-shortcut.md` with this structure:

```markdown
# Shortcut risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (shortcut)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline. Then ≤ 200 words of summary.]

## Findings

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Pattern type**: COMPAT SHIM | HARDCODE | DUPLICATED LOGIC |
  SOURCE/ARTIFACT CONFUSION | SYMPTOM MASK | TEST SHORTCUT |
  SCHEMA SHORTCUT | DEFER-AS-WORKAROUND | TRANSACTION SHORTCUT |
  PRE-RESEARCH CARRYOVER | OPERATOR CONVENIENCE | DEFENSIVE
  OVERENGINEERING | OTHER
- **Section of proposal**: where the shortcut appears
- **Description**: what the shortcut is
- **Why it matters**: what breaks if the shortcut is accepted
- **Recommendation**: specific fix — or "accept, not actually a
  shortcut because [reason]"

[Repeat for each finding, numbered.]

## Overall assessment

[How findings combine into the verdict. Remember: a proposal that
replaces one shortcut with another is NOT LOW, even if both
shortcuts are "fine in isolation."]

## What a LOW verdict requires

The verdict is LOW if the proposal's design pulls its weight at
every layer — no deferred complexity masked as "out of scope,"
no JSONB dumping grounds, no plausibly-but-unproven thresholds, no
carryover of wrong shapes from the pre-research draft.

The verdict is MEDIUM if there are fixable shortcuts the proposal
can address with small edits.

The verdict is HIGH if the proposal's design depends on shortcuts
that, if removed, would require a new design.
```

## Anti-goals

- **Do not evaluate safety or scope** — audit risk and scope risk
  cover those. Your lane is "is the design pulling its weight
  everywhere, or are there hidden shortcuts"
- **Do not rewrite the proposal**
- **Do not hedge**
- **Do not exceed 2500 words**
