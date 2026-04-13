# Humility-specific synthesis

Mapping `research/01-problem-space.md` findings to Humility's specific
context, informed by `NOTES.md`, user decisions from `DECISIONS.md#D4`,
and the emerging OCR requirement.

## Source material

- `research/01-problem-space.md` — broad problem-space taxonomy
- `research/04-ocr-backends.md` — OCR backend comparison and shortlist
- `NOTES.md` — discovered server facts from inspection
- `DECISIONS.md#D4` — MVP scope answers from user
- User conversation — activity tracking, waitlists, officer structure

## User decisions (from synthesis gate)

1. **Chapter membership selectivity**: **(c) Full application review** —
   multi-question form per chapter. Each chapter defines its own form;
   the GUILD TEMPLATE `applications` channel pattern is representative
   of shape, not content.

2. **Data retention**: **(a) Keep everything forever** — applications,
   ticket transcripts, chapter membership history, activity logs.
   Design for durable storage in Postgres with soft deletes, no TTL.

3. **Most acute pain today**: Applications + Tickets + Chapter
   provisioning, all three. Plus **activity tracking with OCR** as a
   new primary requirement.

4. **Moderation**: No mods currently exist. The `Moderator` role is
   empty. The server has `Staff` + chapter-specific `Chapter Officer`
   roles. Chapter officers handle chapter-level operations.

5. **Waitlist**: Applications need a waitlist state — not just
   pending/approved/denied/interview.

6. **Activity tracking**: User currently tracks per-member daily activity
   points by hand in a spreadsheet. Wants: upload screenshots to
   Discord, OCR extracts per-player points, system flags members below
   a configurable threshold. This is a *new* primary requirement not
   in the original scope.

## Four peer subsystems

The project requires four distinct subsystems, all peer-level:

### 1. Applications

**What the research found**: The server has a hidden `applications`
channel in the GUILD TEMPLATE, chapter roles (Officer, Member,
Applicant), but no live instances. The verification flow (Captcha.bot →
Guest → Member) handles server entry, but chapter membership is a
separate workflow.

**Humility-specific needs**:
- Per-chapter application forms (multi-question, chapter-defined)
- Application states: pending → claimed → interview → approved/denied/waitlisted
- Waitlist is a holding state — officer can pull back and decide later
- Officers (not moderators) review applications
- Web UI for forms (richer than Discord modals)
- Approval triggers role assignment (Chapter Member, Chapter Applicant removal)

### 2. Tickets

**What the research found**: HumilityTicketBot (ticketsbot.net) is
broken. The support channel has a stale panel. Ticket logs show minimal
history (3 entries over 4 years). A `Tickets v2` role exists with 0
members.

**Humility-specific needs**:
- Support ticket type (general help)
- Report ticket type (member reports to staff)
- Application-related ticket type (questions about applications)
- Moderator ticket type (routes to staff, not chapter officers)
- Ticket transcripts persisted forever (per retention decision)
- Ticket-to-application promotion (if someone accidentally tickets
  instead of applying)

### 3. Chapter provisioning

**What the research found**: The GUILD TEMPLATE category has the full
channel set. Chapter roles exist but are empty. No active chapters.

**Humility-specific needs**:
- Create a chapter = clone GUILD TEMPLATE category + assign chapter roles
- Chapter lifecycle: create → active → archive
- Chapter officers have elevated permissions in their chapter
- Server-wide Staff and Administrators always retain override access
- Role hierarchy: Chapter Officer > Chapter Member > Chapter Applicant > Chapter Public
- Provisioning should be automated (CLI or web UI trigger)

### 4. Activity tracking (OCR)

**What the research found**: AmariBot handles Discord-side XP/leveling
(explicit keep). The user's actual pain is in-game activity tracking
done by hand in spreadsheets.

**Humility-specific needs**:
- Upload game screenshots to Discord
- OCR extracts per-player activity points from screenshots
- System stores daily activity logs per member per chapter
- Configurable thresholds per chapter
- Flag members below threshold
- Post flags to officer channel
- Activity rules are per-chapter configuration (stored in DB, not YAML —
  officers edit from Discord, not Git)

**OCR backend**: Research is now complete
(`research/04-ocr-backends.md`). The strongest shortlist is:
**PaddleOCR** as the best self-hosted candidate to benchmark first,
**Google Cloud Vision** as the best managed OCR baseline, and **one
LLM-vision track** (`Gemini Vision` or `Claude Vision`) as a
structured-extraction comparison with strict verification. The proposal
should keep OCR as an abstraction boundary and defer the final backend
choice until Humility benchmarks a retained corpus of real screenshots.

## Open questions resolved

| Question | Answer |
|----------|--------|
| Applications for server or chapter? | Chapter membership |
| What is a chapter? | In-game guild, represented as Discord category + roles |
| Data retention? | Forever, soft deletes only |
| Moderators? | None currently; chapter officers handle chapter ops |
| Primary game? | Varies — the system must be game-agnostic |
| Waitlist? | Pre-decision holding state, not post-approval queue |

## Defaults (not contradicted by user)

- Chapter officers handle chapter-level moderation
- Reports to staff are private (not anonymous)
- Staff always retains override access to chapter spaces
- Privacy: gated server (lobby/rules visible pre-verification)
- Single Humility server with many chapters (not multi-tenant)

## Requirements for proposal phase

The proposal must address all four subsystems as peer-level concerns.
Activity tracking implies:
- Dependency on a vision/OCR service (backend TBD — awaiting
  `research/04-ocr-backends.md`)
- Per-chapter activity rules (DB-stored, officer-configurable)
- Separate cost modeling once OCR backend is selected

## Cost and infrastructure implications

- Forever retention → Postgres schema needs soft deletes, archive tables
- OCR → external API or self-hosted costs (TBD pending backend research)
- Web UI is v1 scope → need frontend stack decision
- Cloud-hosted daemon → stateless container + managed database

## Proposal-stage OCR decision boundary

1. **OCR backend choice** — research is complete. Candidates narrowed
   to: (a) a classical OCR path centered on `PaddleOCR`; (b) a managed
   OCR baseline using `Google Cloud Vision`; (c) one LLM-vision
   comparative track (`Gemini Vision` or `Claude Vision`) with strict
   verification. Final backend selection still requires corpus-based
   evaluation and is not settled in synthesis.
