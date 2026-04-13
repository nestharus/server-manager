# Risk assessment prompt — SCOPE risk for proposals/01-v1-scope.md

## Hard rules (read these first)

**YOU are the scope-risk assessor. YOU do the assessment yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is a single markdown file: `risk/01-scope.md`.

- **DO** read `proposals/01-v1-scope.md` in full
- **DO** read `DECISIONS.md`, `AGENTS.md`, `NOTES.md`, and the
  research documents (`research/01-*.md`, `research/02-*.md`,
  `research/04-*.md`) for context
- **DO** write the assessment to `risk/01-scope.md` using your Write
  tool
- **DO NOT** modify any file other than `risk/01-scope.md`
- **DO NOT** rewrite the proposal
- **DO NOT** launch subprocesses
- **DO NOT** print progress to stdout

## What you're assessing

Your job is to identify **scope risk** — whether the proposed scope
is reasonable for the problem, the team, and the runway.

Answer each of these:

1. **Too ambitious?** Does v1 try to deliver more than can reasonably
   ship in a clean first release? List specific features or
   subsystems that are borderline and would be safer cut.
2. **Too narrow?** Does v1 deliver enough to actually solve the user's
   pain, or is it shipping a skeleton that still leaves them on
   spreadsheets / dead bots? What would be the first post-launch
   complaint?
3. **Critical path**: is the sequencing (Option C, foundations first)
   actually the critical path? Is there a phase that blocks all
   subsequent phases, and does the proposal acknowledge that?
4. **Feature coupling**: does the proposal entangle features that
   should be independent? For example, does chapter provisioning
   require applications to be built first, creating a false
   dependency?
5. **Downstream work**: does the proposed design create commitments
   the team can't afford later? Watch for expensive-to-change
   schema choices, expensive-to-rewrite mutation helpers, and
   expensive-to-migrate form storage.
6. **Anti-scope leakage**: the proposal lists features explicitly
   out of v1 (§14). Are any of those features actually required to
   make v1 work, and are being smuggled in as "we'll add it later"?
7. **MVP fit for Humility specifically**: the research said Humility
   is 84 members with zero populated chapters. The proposal's
   database schema and feature surface would also fit a 10k-member,
   50-chapter org. Is the scope right-sized for the actual server,
   or is it building for a hypothetical 10x version?
8. **Implementation budget**: is the proposal achievable without a
   team — this is a one-person (plus agent) effort. Are there
   subsystems that a single human + agent can't reasonably stabilize
   before the next pain point emerges?
9. **Integration risk with existing bots**: Captcha.bot and AmariBot
   are explicit keeps. Does the proposal describe how the new daemon
   interacts with them (or at least doesn't collide)? Is the scope
   of "replace Gather and ticketsbot.net" actually bounded, or does
   it creep into Captcha.bot's territory by accident?
10. **Testing scope**: v1 requires a separate staging guild per
    §11. Is that realistic scope for the project, or is it
    meta-scope that doesn't get built and leaves the real
    implementation untested?
11. **Staging environment cost**: a staging Discord guild plus a
    staging Supabase project plus a staging Railway service is
    overhead. Is the proposal paying for scope it doesn't need?
    Conversely, is cutting this a false economy?
12. **"Forever retention" scope implication**: D4 locked forever-
    retention. Does the schema actually handle that sustainably, or
    does it just omit TTLs and hope? At Humility's scale this is
    probably fine, but is the proposal explicit about the growth
    model?
13. **Cost vs benefit per subsystem**: for each of the four
    subsystems (applications, tickets, activity, provisioning),
    is it justified against the research's documented pain?
    Specifically: tickets have historical volume of 3 test tickets
    in 4 years. Is building 4 ticket types in v1 justified, or
    should some be deferred?
14. **Proposal completeness**: does §17 (cost model) realistically
    reflect operational cost, or does it understate? For example,
    is a staging Supabase project actually free, or does it also
    need Pro tier?
15. **Any other scope concern** — call out anything where the
    proposed scope looks too big or too small for the actual
    situation.

## Output format

Write `risk/01-scope.md` with this structure:

```markdown
# Scope risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (scope)

## Verdict

**LOW** | **MEDIUM** | **HIGH**

[One-sentence headline. Then ≤ 200 words of summary.]

## Findings

### Finding N — <short title>

- **Severity**: LOW | MEDIUM | HIGH
- **Direction**: TOO BIG | TOO SMALL | ENTANGLED | OTHER
- **Section of proposal**: which subsection this applies to
- **Description**: what the scope concern is
- **Why it matters**: concrete impact on the project
- **Recommendation**: specific cut, add, or reshape — or "accept"

[Repeat for each finding, numbered.]

## Overall assessment

[How findings combine into the verdict.]

## What a LOW verdict requires

The verdict is LOW if the scope is credibly achievable, proportionate
to the problem, and does not entangle or starve features.

The verdict is MEDIUM if the scope needs trimming or rebalancing but
is not fundamentally wrong.

The verdict is HIGH if the scope is so wrong (too ambitious or too
narrow) that the proposal should be rewritten before implementation.
```

## Anti-goals

- **Do not evaluate architectural correctness** — that's audit risk's
  job for safety and shortcut risk's job for hacks. Your lane is
  "is this the right amount of work, sequenced correctly, targeting
  the right problems"
- **Do not propose new features** — you're assessing the existing
  scope, not expanding it
- **Do not hedge**
- **Do not exceed 2500 words**
