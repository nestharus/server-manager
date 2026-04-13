# Risk assessment prompt — AUDIT risk for proposals/01-v1-scope.md

## Hard rules (read these first)

**YOU are the audit-risk assessor. YOU do the assessment yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/01-audit.md`.

- **DO** read `proposals/01-v1-scope.md` in full. It is your primary
  input.
- **DO** read `DECISIONS.md` (for context on why this shape exists),
  `AGENTS.md` (for the project's operational rules including The
  Live Server Principle), `NOTES.md` (for the live server context),
  and the research documents (`research/01-*.md`, `research/02-*.md`,
  `research/04-*.md`) as needed to ground claims.
- **DO** write the assessment to `risk/01-audit.md` using your Write
  tool.
- **DO NOT** modify any file other than `risk/01-audit.md`
- **DO NOT** write the proposal itself — you're evaluating it, not
  revising it
- **DO NOT** launch subprocesses
- **DO NOT** print progress commentary to stdout or any log

## What you're assessing

Your job is to identify **audit risk** — safety, security, privacy,
and data-integrity risks introduced by `proposals/01-v1-scope.md`.

Ask yourself these specific questions and answer them:

1. **Credential management**: does the proposal properly isolate the
   bot token, Supabase service key, Google Cloud Vision key, and
   Gemini API key? Are they loaded from env vars only, never committed
   to the repo, never logged, and never included in audit events or
   error messages?
2. **Destructive operations**: the bot has Administrator permission
   on the live Humility server. What destructive operations are
   possible, and does the proposal describe how they are bounded?
   Specifically: role mutations, channel creation/deletion,
   permission overwrite changes, member role assignments, channel
   message deletion, channel archival.
3. **Bounded mutation patterns**: does the proposal actually prevent
   mass mutations, or does it just say "we'll be careful"? Is there
   a single mutation wrapper with enforceable preconditions, or can
   code paths bypass it?
4. **SQL injection / data integrity**: all database writes go through
   the daemon. Does the proposal describe parameterized queries,
   schema constraints, foreign-key discipline, and transaction
   boundaries where required? Are there any paths where user input
   could land in a query string unescaped?
5. **User-uploaded images**: the activity-tracking subsystem accepts
   screenshot uploads. What's the attack surface? Can a malicious
   image exhaust the OCR pipeline, exploit an image-parsing
   dependency, or trigger a vision-API prompt injection?
6. **Privacy**: the system stores Discord member identities, in-game
   names, application answers, ticket transcripts, and OCR'd player
   names. Is there any PII being logged that shouldn't be? Any data
   flowing to a third party (Google, Gemini) that exceeds the scope
   of the task? Any retention issues given the "forever retention"
   decision?
7. **Discord rate limits**: the daemon could theoretically flood the
   Discord API during a bad code path (e.g., reconciliation loop
   bug, mass-role-mutation bug). Does the proposal describe
   rate-limit handling and burst limits for the specific operations
   that are most at risk — role creation, channel creation,
   overwrite updates during provisioning?
8. **Third-party vendor kill switches**: if Google Vision or Gemini
   go down, what's the failure mode? Does the daemon gracefully
   degrade, or does it wedge the entire activity pipeline?
9. **Token leakage in error reporting**: structured logs are described
   in §10. Are there any paths where a token or secret could make
   it into a log line, alert payload, or audit event?
10. **Transcript privacy**: ticket and application messages are
    persisted. Is there any path where a user's private ticket
    conversation could leak into a public channel, into a log, or
    into the OCR subsystem?
11. **Provisioning rollback**: the proposal says rollback of failed
    provisioning is non-destructive. Is "leave orphaned roles and
    channels on failure" actually safe, or does it create audit/
    permission hazards?
12. **Staging vs production separation**: the proposal requires a
    separate staging Discord guild and staging Supabase project. Is
    the separation actually enforceable, or can code paths touch
    production when developer intends staging?
13. **Audit trail integrity**: `audit_events` is supposed to be
    append-only. Is that actually enforced (DB constraints, RLS,
    application logic)? Can audit rows be modified or deleted once
    written?
14. **OCR hallucination as a security issue**: a vision LLM
    hallucinating rows in an activity import could silently award
    a non-existent player points, or zero out a real player. Does
    the proposal's hallucination-control flow actually prevent this,
    or is it just "we log it"?
15. **Any other audit-risk concern you find** — this list is not
    exhaustive. Call out anything that looks unsafe, insecure, or
    data-integrity-hazardous.

## Output format

Write `risk/01-audit.md` with this structure:

```markdown
# Audit risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (audit)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline justification. Then ≤ 200 words of summary.]

## Findings

For each concern you identify:

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Section of proposal**: which subsection this applies to
- **Description**: what the concern is
- **Why it matters**: concrete blast radius or exploit path
- **Recommendation**: what change in the proposal would fix it, if
  any — or "accept as written, LOW severity"

[Repeat for each finding, numbered.]

## Overall assessment

[Summary of how the findings combine into the verdict. If any
individual finding is MEDIUM or HIGH, the overall verdict cannot be
LOW unless you explicitly justify why the mitigation prevents it from
materially affecting the proposal.]

## What a LOW verdict requires

The verdict is LOW if and only if every material concern has either
(a) no realistic attack/data-loss path given the proposal's described
controls, or (b) a mitigation already described in the proposal that
reduces the residual risk to negligible.

The verdict is MEDIUM if one or more findings require proposal
changes but the changes are contained and don't force a rewrite.

The verdict is HIGH if one or more findings force a rewrite, block
implementation, or indicate a fundamental unsafe assumption.
```

## Anti-goals

- **Do not rewrite the proposal.** You are an assessor. Recommendations
  should be minimal edits, not whole new designs.
- **Do not make risk evaluations that ignore the proposal's stated
  mitigations.** Read carefully — if the proposal says "bounded
  mutation wrapper enforces preconditions," evaluate whether that
  claim is credible given the design, not whether the risk exists in
  a generic system without that control.
- **Do not return MEDIUM or HIGH without a concrete finding.** A
  vague unease is LOW. A specific exploit or data-loss path is
  MEDIUM or HIGH.
- **Do not hedge.** Pick a verdict and justify it.
- **Do not write more than 2500 words.** Be specific, not verbose.
