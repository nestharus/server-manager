# Pitch Deck Ban Violations

Scope notes:
- `[BRACKETED: ...]` placeholders were ignored.
- `---` horizontal rules were ignored.
- En dashes were not flagged.
- A line can appear in multiple sections when one passage violates multiple hard bans.

| Category | Count | Notes |
|---|---:|---|
| Em dash characters | 50 | 50 `—` characters across 40 lines |
| Sentence-initial banned openers | 1 | One sentence starts with a banned opener |
| Triads in prose | 16 | Clear three-item prose triads |
| Pseudo lists from parallel clauses | 4 | Repeated-clause list shapes |
| Three consecutive sentences with same opening word | 1 | One three-sentence sequence |
| Three consecutive sentences with same grammatical frame | 1 | Same three-sentence sequence |
| Vague modal hedges | 4 | All are `could` |
| Throat clearing phrases | 3 | Prefatory meta/setup lines |
| Posturing frames | 4 | Self-signaling honesty/status framing |
| Cliches | 4 | Startup / venture deck cliches |
| Moralizing or status language | 4 | Honesty-posture and status wording |
| Performative intent sentences | 7 | Sentences that summarize, signal, or land the point |

## 1. Em Dash Characters

- L9 (1x): `Meanwhile, a harassment report has been sitting in a ticket bot for four days — nobody knows if it was claimed because the bot's dashboard was down yesterday.`
- L17 (1x): `When multiple officers can review the same intake queue, two reviewers independently evaluate the same application without knowing the other has started — duplicating scarce volunteer effort.`
- L31 (2x): `their workflows are action-based — open, claim, close — not lifecycle-based.`
- L35 (2x): `a general-purpose compliance engine — configurable rules, chapter-specific thresholds, automatic consequence workflows — is still missing.`
- L47 (2x): `Gather — the one reviewed application product that had form versioning and a richer submission lifecycle — is deprecated`
- L51 (1x): `the proposal requires — capabilities that were either missing or unstable before.`
- L65 (2x): `Humility — the design reference community — had 83 members during the original operational sweep`
- L74 (2x): `The weekly compliance ritual — screenshot review, spreadsheet transcription, threshold comparison, individual DMs — is the single largest recurring volunteer-time cost`
- L80 (1x): `**§5 Chapter lifecycle** — every subgroup created today increases future cleanup cost`
- L81 (1x): `**§6 Activity tracking** — the weekly spreadsheet ritual is a primary burnout driver`
- L82 (1x): `**§3 Case routing** — stalled harassment reports erode community trust, stalled appeals leave members in limbo`
- L95 (2x): `core operational primitives — intake, cases, rosters, permissions, audit —`
- L119 (2x): `When Discord changes a feature — or when a community wants to export their operational history — neither the workflows nor the data are locked in a vendor-specific format.`
- L127 (1x): `Two independently start reviewing — one DMs the applicant for more information, the other adds notes in a spreadsheet.`
- L129 (1x): `the system locks ownership — no one else can claim the same application.`
- L137 (2x): `configured compliance rules — attendance minimums, rank requirements, activity thresholds — on a scheduled basis.`
- L139 (1x): `The system never auto-confirms compliance — it provides structured data, and officers make the final call on contested cases.`
- L145 (1x): `Temporary overrides have explicit expiration dates — when they expire, the system flags them for resolution`
- L159 (1x): `Deep feature in one lane — tickets, forms, attendance thresholds, backups, or roster`
- L160 (1x): `Cannot copy the integrated substrate — a feature add sits next to the existing tool's data model`
- L181 (1x): `The ask is not revenue — it is commitment to build the Phase 1 governance foundation`
- L185 (1x): `community funding — GitHub Sponsors, Open Collective, or equivalent`
- L195 (1x): `competitors already monetize around (claiming, retention, alliance capacity, backups — ... )`
- L216 (1x): `permission drift detection — the operational core that eight application tools, nine ticket tools, and eight multi-unit suites compete on today`
- L248 (1x): `the weekly spreadsheet ritual does not get replaced — it gets augmented with a new review queue.`
- L250 (1x): `The system never auto-confirms compliance — officers make the final call on contested cases.`
- L276 (1x): `Run your most urgent operations through the system — open cases without them disappearing into DMs`
- L282 (1x): `Claim and review applications with exclusive ownership — no more duplicate reviews`
- L293 (1x): `Decide applications with full adjudication — interviews, waitlists, approvals, denials, and mandatory reasons`
- L302 (2x): `Apply proportional compliance consequences — notification, flag for review, or automatic probation — with officer confirmation or override`
- L314 (1x): `Humility is the design reference community — 83 members during the original operational sweep`
- L354 (1x): `Operational continuity — a community-owned alternative to vendor-dependent bot stacks`
- L362 (2x): `The people who run gaming communities today — who live with the fragmentation, the spreadsheets, and the burnout — know best`
- L365 (1x): `**Describe your worst operational pain point** — the thing that makes you dread logging in`
- L376 (1x): `**Detailed phase breakdown and value slices** — ...`
- L377 (1x): `**Full risk register** ... — ...`
- L378 (1x): `**Competitive research methodology** ... — ...`
- L379 (1x): `**Problem axes** ... — ...`
- L380 (1x): `**System design details** ... — ...`
- L381 (1x): `**Locked infrastructure decisions** ... — ...`

## 2. Sentence-Initial Banned Openers

- L37: `But governance visibility stops at logs or backups.`

## 3. Triads In Prose

- L15: `Harassment reports, appeals, and recruitment issues live in DM threads...`
- L31: `open, claim, close`
- L31: `Per-category escalation rules, mandatory resolution reasons, and time-based accountability`
- L35: `configurable rules, chapter-specific thresholds, automatic consequence workflows`
- L74: `ticket triage without SLA visibility, reviewer-collision reconciliation in intake, and permission-drift forensics after the fact`
- L137: `attendance minimums, rank requirements, activity thresholds`
- L137: `confirm, override, or request more evidence`
- L145: `reconcile (apply the intent to Discord), accept (update the intent to match reality), or acknowledge (mark as known, defer for later)`
- L147: `which permissions are intentional, which are under review, and which were accepted as exceptions`
- L162: `a claim-lock, a drift detector, or a mandatory resolution reason`
- L260: `Clear contribution entry points, public roadmap, and documented governance`
- L276: `audit permissions against declared intent, create chapters without manual one-off setup, and change operational rules on a live server`
- L294: `screenshot evidence, game APIs, and manual reports`
- L360: `Time, feedback, and early adoption.`
- L362: `the fragmentation, the spreadsheets, and the burnout`
- L381: `Vultr VKE, Google Cloud Vision primary + Gemini 3 Flash Preview fallback, cloud-hosted architecture`

## 4. Pseudo Lists From Parallel Clauses

- L15: `with no durable ownership, no time-based accountability, and no privacy guarantees`
- L21: `Every mandatory review step, every duplicate notification, every manual data entry task`
- L27: `one bot for tickets, one for applications, one for moderation logs, one for reaction roles`
- L147: `which permissions are intentional, which are under review, and which were accepted as exceptions`

## 5. Three Consecutive Sentences With Same Opening Word

- L131: `No duplicate reviews. No conflicting decisions. No lost context.`

## 6. Three Consecutive Sentences With Same Grammatical Frame

- L131: `No duplicate reviews. No conflicting decisions. No lost context.`

## 7. Vague Modal Hedges

- L226: `**What could happen.**`
- L236: `**What could happen.**`
- L246: `**What could happen.**`
- L256: `**What could happen.**`

## 8. Throat Clearing Phrases

- L201: `Honest cost buckets from the committed infrastructure decisions...`
- L222: `The executive roadmap's risk register names seven specific risks... The four most material to investors are surfaced here...`
- L374: `The main deck above addresses the core investor spine. The following material is expected to surface in Q&A...`

## 9. Posturing Frames

- L97: `**Honest framing.**`
- L175: `Both are described honestly below; the project will not pretend either is already validated.`
- L201: `Honest cost buckets from the committed infrastructure decisions...`
- L330: `The strategic artifacts represent the work a well-capitalized team would otherwise spend its first two quarters producing...`

## 10. Cliches

- L61: `This is not a Discord-wide TAM play. The market story is a bottoms-up wedge with a credible expansion path.`
- L160: `Integration is the moat`
- L179: `The current proof of concept is the Humility community itself...`
- L314: `The design did not start from a whiteboard; it started from the daily operational work of running this community.`

## 11. Moralizing Or Status Language

- L97: `**Honest framing.**`
- L175: `Both are described honestly below; the project will not pretend either is already validated.`
- L201: `Honest cost buckets from the committed infrastructure decisions...`
- L330: `a well-capitalized team`

## 12. Performative Intent Sentences

- L97: `**Honest framing.**`
- L175: `Both are described honestly below; the project will not pretend either is already validated.`
- L181: `The ask is not revenue — it is commitment to build...`
- L222: `The four most material to investors are surfaced here with mitigation plans...`
- L330: `That work is already done.`
- L368: `The goal is a platform that earns adoption by solving real problems for the people who do the work. Your experience is the input that makes that possible.`
- L374: `The main deck above addresses the core investor spine.`
