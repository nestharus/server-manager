# Decision log

Append-only log of architectural and workflow decisions for this project.
Each entry: **D#** — date — title — context — decision — consequences.

---

## D1 — 2026-04-11 — Adopt research-first workflow from ~/work/AGENTS.md

**Context**: Initial work on this project jumped straight from problem
statements ("I want a Discord bot to manage the server") to solutions
(daemon, applications subsystem, SQLite schema). Several decisions were
made prematurely, before the real guild-management problem space was
researched.

**Decision**:
1. All feature work follows the phased pipeline:
   research → synthesis → proposal → 3x risk → hookpoints → implement
2. Each phase uses a separate agent invocation. Claude Code orchestrates
   and synthesizes; it does not collapse phases.
3. No implementation proceeds unless the proposal has cleared the full
   LOW-risk gate.

**Consequences**:
- Research artifacts live in `research/`, proposals in `proposals/`,
  risk reports in `risk/`
- The current codebase is not treated as validated architecture just
  because it exists
- `discord_cli.py` remains the inspection/control surface while the
  actual design is re-derived from research

---

## D2 — 2026-04-11 — Reject SQLite/local-first as the canonical architecture

**Context**: The earlier daemon draft assumed a local-first SQLite
database. The user explicitly said SQLite is the wrong fit for a 24/7
cloud-hosted service.

**Decision**:
1. The canonical architecture is cloud-hosted, not local-first.
2. The canonical data store must be network-accessible and appropriate
   for a continuously running service; SQLite is not the target system
   for the validated design.
3. Any surviving code from the SQLite draft is historical only until
   hookpoint research proves it should survive.

**Consequences**:
- Proposal phase must assume a cloud-appropriate storage layer
- Deployment and operational concerns are first-class, not deferred
- SQLite-backed daemon code is treated as pre-research draft state

---

## D3 — 2026-04-11 — Preserve, do not delete, pre-research drafts

**Context**: When pivoting from the build-first approach to
research-first, there is a temptation to delete the existing daemon and
draft docs immediately. That would destroy potential hookpoints and
historical context before phase 5 evaluates them.

**Decision**:
1. Preserve the current pre-research draft artifacts for now:
   `daemon/`, `forms/`, `docs/DAEMON_DESIGN.md`,
   `docs/APPLICATIONS_SKETCH.md`, and related notes.
2. Do not extend those draft artifacts before proposal + risk +
   hookpoint phases are complete.
3. Let hookpoint research decide what is reusable, what is rewritten,
   and what is deleted.

**Consequences**:
- Pre-research code remains available for comparison but is not treated
  as approved design
- Hookpoint research has real material to evaluate instead of guesses
- The reset is procedural, not destructive

---

## D4 — 2026-04-11 — MVP scope answers (user decisions after phase 1)

**Context**: After `research/01-problem-space.md` landed, the user
answered the first scope-setting questions and added a new operational
pain point around activity tracking.

**Decision**:
1. Chapter intake defaults to full application review with a
   multi-question form (`c`), not open opt-in or a short officer ticket.
2. Operational data retention is indefinite (`a`): keep applications,
   ticket transcripts, chapter history, and related operational records.
3. Immediate MVP priorities are applications, tickets, and chapter
   provisioning. Moderation is not the current first build because
   Humility has officers but no moderators right now.
4. Chapter operations also need waitlists and activity management.
   Activity points are currently tracked manually in a spreadsheet;
   the future system should support screenshot uploads, OCR extraction,
   and flagging members who miss chapter-defined targets.
5. The exact OCR backend is not decided yet and needs its own narrow
   phase-1 research pass.

**Consequences**:
- The proposal should treat chapter provisioning as a first-class
  subsystem, peer with applications and tickets, not a v2 afterthought.
- Long-term retention and auditability are core requirements, not
  optional add-ons.
- Waitlists and officer workflows are part of initial scope.
- Activity thresholds are per-chapter configuration.
- OCR backend selection is deferred to dedicated research.
