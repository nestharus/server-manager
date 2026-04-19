# Pitch Deck Hard-Ban Scan

Source: `product-strategy/pitch deck.md`  
Rules: `product-strategy/WRITING_SKILL_MASTER.md` -> `Non negotiables`

## Scope Notes

- Preserved and not flagged: `---` horizontal rules
- Preserved and not flagged: `[BRACKETED: ...]` placeholders
- En dashes are not flagged as em dashes
- Prose-only checks exclude headings, table rows, and placeholder-only lines
- Sentence-like bullets are included when they contain a hard-ban violation

## Summary Table

| Category | Count | Status |
|---|---:|---|
| 1. Em dash characters | 0 | Pass |
| 2. Sentence-initial banned openers | 0 | Pass |
| 3. Triads in prose | 28 | Fail |
| 4. Pseudo lists from parallel clauses | 3 | Fail |
| 5. Three consecutive sentences with same opening word | 0 | Pass |
| 6. Three consecutive sentences with same grammatical frame | 3 | Fail |
| 7. Vague modal hedges | 0 | Pass |
| 8. Throat clearing phrases | 3 | Fail |
| 9. Posturing frames | 2 | Fail |
| 10. Cliches | 6 | Fail |
| 11. Moralizing or status language | 0 | Pass |
| 12. Performative intent sentences | 7 | Fail |

## 1. Em Dash Characters

None found.

## 2. Sentence-Initial Banned Openers

None found.

## 3. Triads in Prose

- `L9`: `You pull up your chapter's attendance spreadsheet, open three different screenshot channels, and start cross-referencing names against thresholds.`
- `L13`: `Officers spend hours every week copying activity data from screenshots into spreadsheets, comparing against thresholds, and chasing down members who are behind.`
- `L27`: `Officers today solve these problems by stitching together five or more disconnected tools: a ticket bot, an application bot, a moderation-log bot, a reaction-role bot, a spreadsheet for compliance tracking, and DMs for everything that doesn't fit.`
- `L31`: `Ticket Tool, Helper.gg, Discord Tickets, and Modmail handle case creation and transcripts...`
- `L33`: `Application tools like Appy, Application Bot, and ApplicationForms provide form submission and dashboard review...`
- `L35`: `Activity and roster tools like Throney, Guild Manager, and Raid-Helper track attendance and participation...`
- `L35`: `Officers still edit attendance in spreadsheets and stitch together manual proof handling across Discord, bots, and optional guild websites.`
- `L37`: `Permission and security bots like Wick, Dyno, Carl-bot, and Xenon automate roles, monitor dangerous permissions, and back up server state.`
- `L49`: `...a single decision chain spanning intake, cases, chapters, permissions, and compliance...`
- `L51`: `Discord's interaction APIs (slash commands, components v2, modal select components in discord.py 2.7+) now support the intake, review, and reconciliation UX...`
- `L53`: `Claiming, transcript depth, log history, exports, alliance capacity, and backup/restore are consistently paywalled...`
- `L65`: `Gaming guilds with roughly 50–500 members that run chapter operations, application review, activity compliance, and multi-officer governance.`
- `L74`: `The weekly compliance ritual (screenshot review, spreadsheet transcription, threshold comparison, individual DMs) is the single largest recurring volunteer-time cost...`
- `L76`: `Premium gating concentrates around exactly the features operators need most: claim workflow, transcript delivery, log retention, exports, alliance capacity, and backup/restore...`
- `L95`: `Each adjacent segment shares the core operational primitives (intake, cases, rosters, permissions, audit)...`
- `L105`: `Humility replaces the fragmented bot stack with a single system where intake, cases, compliance, permissions, chapters, and governance share a unified audit chain.`
- `L111`: `Every operational decision is recorded with actor, inputs, prior state, and governing policy version...`
- `L113`: `Operators declare what permission state, chapter structure, and compliance rules should be.`
- `L129`: `The reviewer sees the applicant's trust profile, prior applications, and relevant chapter roster state in one view.`
- `L129`: `They can add notes, request a private interview, approve with a mandatory reason, deny with a mandatory reason, or place the applicant on a waitlist.`
- `L135`: `Every week, an officer opens a screenshot channel, downloads images, manually transcribes activity data into a spreadsheet, compares each member against chapter-specific thresholds, identifies violations, and DMs members individually.`
- `L137`: `The system evaluates each member against the chapter's configured compliance rules (attendance minimums, rank requirements, activity thresholds) on a scheduled basis.`
- `L179`: `The design, problem definition, competitive landscape, and strategic roadmap are complete.`
- `L195`: `Tiered pricing by community size would match the premium-gating patterns competitors already monetize around: claiming, retention, alliance capacity, and backups.`
- `L216`: `At Phase 2, the system runs structured applications with reviewer ownership, per-category ticket state machines, chapter provisioning from templates, and permission drift detection...`
- `L230`: `Phase 1 is explicitly a substrate investment (trust, authority, causal audit, policy versioning)...`
- `L314`: `Humility is the design reference community... with real chapter scaffolding, real applications history, and the exact operator pain profile the proposal targets.`
- `L346`: `At Phase 2, the platform runs structured applications, per-category ticket state machines, chapter provisioning, and permission drift detection...`

## 4. Pseudo Lists From Parallel Clauses

- `L39`: `Tickets are transcript-first, permissions are event-log-first, and broader platforms expose local workflow history rather than a chain that follows one decision across applications, rosters, permissions, and compliance consequences.`
- `L197`: `ship Phase 2 to design-partner communities → measure which operator features cross the threshold of "I would rather pay than re-assemble the bot stack" → decide whether to offer the hosted tier based on that evidence.`
- `L250`: `Original screenshots are always preserved; officers can correct extractions; corrections are attributed.`

## 5. Three Consecutive Sentences With Same Opening Word

None found.

## 6. Three Consecutive Sentences With Same Grammatical Frame

- `L127`: `Three officers see it in a shared channel. Two independently start reviewing. One DMs the applicant for more information, the other adds notes in a spreadsheet.` All three use the same count-subject -> action beat.
- `L240`: `Scope a one-time migration tool inside VS-008 (permission intent) engineering work. Flag first-run classification as a known onboarding cost in Phase 2 go-to-market communication. Start with design-partner communities that have explicit operator capacity for the initial classification pass.` All three are imperative verb -> object sentences.
- `L276`: `Cases stay visible instead of disappearing into DMs. Permission audits run against declared intent, and chapter creation uses templates. Live-policy changes protect in-flight work instead of breaking it.` All three use the same noun-subject -> present-tense result frame.

## 7. Vague Modal Hedges

None found.

## 8. Throat Clearing Phrases

- `L61`: `This is not a Discord-wide market pitch.` Meta framing instead of advancing the claim.
- `L107`: `The design is built on structural commitments investors can evaluate against the competitive field:` Section setup rather than substance.
- `L222`: `Each one below pairs a mitigation plan with the milestone at which the risk is contained.` Pure signposting.

## 9. Posturing Frames

- `L49`: `Market gaps are documented, not speculative.` Authority-claim framing.
- `L51`: `The technical enablers are mature.` Broad confidence frame without the evidence in the sentence itself.

## 10. Cliches

- `L11`: `This is the daily reality for officers running gaming communities on Discord.`
- `L55`: `...the moment to start is now.`
- `L109`: `The system's database is the source of truth...`
- `L316`: `Why now is the right moment for this team.`
- `L362`: `...which workflows need to feel right from day one.`
- `L368`: `Your experience is the input that makes Phase 2 feel right from day one.`

## 11. Moralizing Or Status Language

None found.

## 12. Performative Intent Sentences

- `L11`: `The problems compound:` Summary throat-clearing line that exists to package the section.
- `L39`: `The fundamental gap: audit is fragmented and local.` Landing sentence.
- `L55`: `The window is finite.` Landing sentence.
- `L97`: `This is a niche first.` Packaging sentence.
- `L131`: `No duplicate reviews, and no conflicting decisions.` Tagline-style payoff sentence.
- `L362`: `This is the stage where community input has the most leverage.` Persuasive framing sentence.
- `L368`: `Your experience is the input that makes Phase 2 feel right from day one.` Closing persuasion sentence.
