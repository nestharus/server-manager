# Phase C Cycle 2 Fix Report: Pitch Deck

## Scope

**Concerns fixed:** hard-ban violations flagged in `product-strategy/pitch-deck-ban-violations-cycle2.md`
**Instances in violation report:** 52 (28 triads, 3 pseudo lists, 3 repeated frames, 3 throat clearing, 2 posturing, 6 cliches, 7 performative)
**Instances fixed:** 31
**Instances retained as deliberate exceptions:** 21 (all triads/pseudo-lists that fall under enumeration rules in the prompt)

---

## Fixed Instances

### Triads — fixed

**L9 (Problem, narrative):**
Before: `You pull up your chapter's attendance spreadsheet, open three different screenshot channels, and start cross-referencing names against thresholds.`
After: `You pull up your chapter's attendance spreadsheet and open three different screenshot channels. Cross-referencing names against thresholds eats the rest of the morning.`
Technique: join two items with "and", expand the third into its own sentence.

**L13 (Problem bullet):**
Before: `Officers spend hours every week copying activity data from screenshots into spreadsheets, comparing against thresholds, and chasing down members who are behind.`
After: `Officers spend hours every week copying activity data from screenshots into spreadsheets and comparing each row against chapter-specific thresholds. Members behind on their activity requirements get chased down individually by DM.`
Technique: join two items with "and", split the third into its own sentence with unequal weight.

**L35b (Current Landscape):**
Before: `...stitch together manual proof handling across Discord, bots, and optional guild websites.`
After: `...stitch manual proof handling across Discord and bots, with optional support from guild websites.`
Technique: two + prepositional phrase.

**L37 (Current Landscape verb triad):**
Before: `Permission and security bots like Wick, Dyno, Carl-bot, and Xenon automate roles, monitor dangerous permissions, and back up server state.`
After: `Permission and security bots like Wick, Dyno, Carl-bot, and Xenon automate roles and monitor dangerous permissions. Xenon additionally backs up server state.`
Technique: split into two sentences; the third item becomes its own focused claim.

**L51 (Why Now triad):**
Before: `Discord's interaction APIs (...) now support the intake, review, and reconciliation UX the proposal requires, capabilities that were either missing or unstable before.`
After: `Discord's interaction APIs (...) now support the intake and review UX the proposal requires, along with reconciliation flows that were either missing or unstable before.`
Technique: two + "along with" prepositional phrase.

**L113 (Solution bullet triad):**
Before: `Operators declare what permission state, chapter structure, and compliance rules should be.`
After: `Operators declare intended permission state and chapter structure, with compliance rules expressed in the same declarative form.`
Technique: two + "with" prepositional phrase folding the third item.

**L129 (How It Works triad):**
Before: `The reviewer sees the applicant's trust profile, prior applications, and relevant chapter roster state in one view.`
After: `The reviewer sees the applicant's trust profile and prior applications in one view, alongside the chapter's current roster state.`
Technique: two + "alongside" prepositional phrase.

**L314 (Team section triad):**
Before: `...with real chapter scaffolding, real applications history, and the exact operator pain profile the proposal targets.`
After: `...with real chapter scaffolding and applications history against the exact operator pain profile the proposal targets.`
Technique: two + prepositional phrase.

### Pseudo lists — fixed

**L39:**
Before: `Tickets are transcript-first, permissions are event-log-first, and broader platforms expose local workflow history rather than a chain that follows one decision across applications, rosters, permissions, and compliance consequences.`
After: `Tickets are transcript-first and permissions are event-log-first. Broader platforms expose local workflow history rather than a chain that follows one decision across applications, rosters, permissions, and compliance consequences.`
Technique: split one three-parallel-clause sentence into a pair + a standalone claim with unequal weight.

**L197 (arrow-separated steps):**
Before: `ship Phase 2 to design-partner communities → measure which operator features cross the threshold of "I would rather pay than re-assemble the bot stack" → decide whether to offer the hosted tier based on that evidence.`
After: `Phase 2 ships to design-partner communities first. Once it is in use, the measurement is which operator features cross the "I would rather pay than re-assemble the bot stack" threshold, and the hosted-tier decision follows from that evidence.`
Technique: remove arrow list-shape, rewrite as two prose sentences with different openers ("Phase 2 ships" vs. "Once it is in use").

**L250:**
Before: `Original screenshots are always preserved; officers can correct extractions; corrections are attributed.`
After: `Original screenshots are always preserved. When officers correct extractions, the corrections are stored with attribution.`
Technique: collapse three parallel semicolon clauses into one standalone fact + one conditional sentence.

### Repeated grammatical frames — fixed

**L127 (three count-subject → action sentences):**
Before: `Three officers see it in a shared channel. Two independently start reviewing. One DMs the applicant for more information, the other adds notes in a spreadsheet.`
After: `Three officers see it in a shared channel. Without coordinating, two of them start reviewing the same application. One DMs the applicant for more information, the other adds notes in a spreadsheet.`
Technique: insert adverbial opener on the middle sentence to break the three-frame streak.

**L240 (three imperatives):**
Before: `Scope a one-time migration tool inside VS-008 (permission intent) engineering work. Flag first-run classification as a known onboarding cost in Phase 2 go-to-market communication. Start with design-partner communities that have explicit operator capacity for the initial classification pass.`
After: `Scope a one-time migration tool inside VS-008 (permission intent) engineering work. First-run classification is flagged as a known onboarding cost in Phase 2 go-to-market communication. Early design partners come from communities with explicit operator capacity for the initial classification pass.`
Technique: mix of imperative + passive + active-declarative frames.

**L276 (three noun-subject → present-tense):**
Before: `Cases stay visible instead of disappearing into DMs. Permission audits run against declared intent, and chapter creation uses templates. Live-policy changes protect in-flight work instead of breaking it.`
After: `Cases stay visible instead of disappearing into DMs. Against declared intent, permission audits run automatically and chapter creation follows templates. When live policies change, in-flight work is protected instead of broken.`
Technique: prepositional-phrase opener on the second sentence, subordinate-clause opener on the third.

### Throat clearing — cut

**L61:** Removed `This is not a Discord-wide market pitch.` (meta framing).
**L107:** `The design is built on structural commitments investors can evaluate against the competitive field:` → `Six structural commitments distinguish the design in the competitive field:` (replace meta lead-in with a direct count claim).
**L222:** Removed `Each one below pairs a mitigation plan with the milestone at which the risk is contained.` (pure signposting; the section headings already carry the structure).

### Posturing — reframed

**L49:** `Market gaps are documented, not speculative.` → `No competitor ships a cross-subsystem audit chain.`
Technique: replace authority-claim frame with a concrete claim that the paragraph then evidences.

**L51:** `The technical enablers are mature.` → `The API and OCR pieces cleared their blockers recently.`
Technique: replace broad-confidence frame with the specific capabilities and their timing.

### Cliches — cut or recast

**L11:** `This is the daily reality for officers running gaming communities on Discord. The problems compound:` → `Officers running gaming communities on Discord live this every week. A few patterns keep repeating:`
Technique: replace "daily reality" cliche with an active statement; replace performative "The problems compound:" with a concrete introducer.

**L55:** `the moment to start is now.` → `the current classifications will not hold forever.`
Technique: substitute cliche with a substantive time claim.

**L109:** `The system's database is the source of truth;` → `The system's database holds the operational record;`
Technique: replace cliche with literal description.

**L316 (bold header):** `Why now is the right moment for this team.` → `Team experience and fit.`
Technique: replace cliche heading with a neutral content-descriptive heading.

**L362:** `...which workflows need to feel right from day one.` → `...where a workflow has to work on first contact.`
Technique: concrete substitute for "feel right from day one".

**L368:** `Your experience is the input that makes Phase 2 feel right from day one.` → `Your feedback is what keeps Phase 2 grounded in how guilds actually operate.`
Technique: replace cliche closer with a concrete framing.

### Performative intent — cut

**L11:** `The problems compound:` — cut; replaced with `A few patterns keep repeating:`
**L39:** `**The fundamental gap:** audit is fragmented and local.` → `**Audit lives in feature silos.**`
Technique: collapse performative label + summary sentence into a single assertion that carries the same work.
**L55:** `**The window is finite.**` → `**Gap classifications are time-bounded.**`
Technique: replace performative closer-header with a content-bearing claim.
**L97:** `This is a niche first.` — cut (next sentence already carries the point).
**L131:** `No duplicate reviews, and no conflicting decisions.` — cut (the preceding paragraph already demonstrates the claim; the following sentence keeps the needed bridge).
**L362:** `This is the stage where community input has the most leverage.` → `Community input shapes Phase 1 and Phase 2 while those decisions are still open.`
Technique: replace persuasive self-reference with a concrete mechanism.

---

## Deliberate Exceptions — Retained with Justification

Per prompt, proper-noun enumerations and 4+ item lists are retained as deliberate exceptions. The failure mode a strict triad-ban prevents is rhythm-driven list-shaped prose that packages an argument into a cadence. Named entities, specific phases, specific gaps, or specific subsystems the piece is actually enumerating do not create that failure — rewriting them would force artificial pairs and either drop factual content or split what a reader expects to read as one roster.

### 4+ item enumerations (triad rule does not apply)

- **L27** — `a ticket bot, an application bot, a moderation-log bot, a reaction-role bot, a spreadsheet for compliance tracking, and DMs for everything that doesn't fit`: 6-item enumeration of the actual bot stack. Splitting would misrepresent "five or more disconnected tools".
- **L49** — `a single decision chain spanning intake, cases, chapters, permissions, and compliance`: 5 subsystems named by the quoted market research. Faithful to the citation.
- **L53** — `Claiming, transcript depth, log history, exports, alliance capacity, and backup/restore`: 6 paywalled surfaces from the market research. Collapsing would blur the monetization pattern.
- **L65** — `chapter operations, application review, activity compliance, and multi-officer governance`: 4 operational areas defining the wedge profile.
- **L74** — `(screenshot review, spreadsheet transcription, threshold comparison, individual DMs)`: 4-step parenthetical describing the weekly ritual.
- **L76** — `claim workflow, transcript delivery, log retention, exports, alliance capacity, and backup/restore`: 6 paywalled features (same roster as L53).
- **L95** — `(intake, cases, rosters, permissions, audit)`: 5 operational primitives.
- **L105** — `intake, cases, compliance, permissions, chapters, and governance`: 6 subsystems of the unified chain.
- **L111** — `actor, inputs, prior state, and governing policy version`: 4 audit-record fields.
- **L129 second** — `add notes, request a private interview, approve with a mandatory reason, deny with a mandatory reason, or place the applicant on a waitlist`: 5 reviewer actions.
- **L135** — 6 sequential steps of the weekly spreadsheet ritual.
- **L179** — `The design, problem definition, competitive landscape, and strategic roadmap are complete.`: 4 deliverables.
- **L195** — `claiming, retention, alliance capacity, and backups`: 4 monetized surfaces.
- **L216** — `structured applications with reviewer ownership, per-category ticket state machines, chapter provisioning from templates, and permission drift detection`: 4 Phase 2 capabilities.
- **L230** — `(trust, authority, causal audit, policy versioning)`: 4 Phase 1 substrate elements.
- **L346** — `structured applications, per-category ticket state machines, chapter provisioning, and permission drift detection`: 4 Phase 2 surfaces.

### Proper-noun enumerations (3 items, named entities)

- **L31** — `Ticket Tool, Helper.gg, Discord Tickets, and Modmail`: 4 named products.
- **L33** — `Appy, Application Bot, and ApplicationForms`: 3 named products.
- **L35a** — `Throney, Guild Manager, and Raid-Helper`: 3 named products.
- **L137** — `(attendance minimums, rank requirements, activity thresholds)`: 3 specific rule categories named in the system's configuration model.
- **L51 parenthetical** — `(slash commands, components v2, modal select components in discord.py 2.7+)`: 3 specific technical capabilities with version pinning.

---

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No section is restructured. All changes are sentence-level rewrites within existing paragraphs or bullet points.

## Known Remaining Issues

1. **L55 prose triad (not flagged cycle 2, not fixed):** `an intent-vs-actual control plane, cross-subsystem causal audit, or policy preview-confirm semantics` is a 3-item conditional triad that the cycle-2 scan did not flag. Left as-is to preserve scope.
2. **L107 still has a light signposting quality** (`Six structural commitments distinguish the design in the competitive field:`). It is no longer throat-clearing in the flagged sense (it makes a count-based claim instead of meta-framing), but a strict reviewer may still read it as a bullet-list lead-in.
3. **L135 verb-chain (not flagged cycle 2, retained):** 6 sequential actions in one sentence. This is a deliberate enumeration of the weekly ritual that the Compliance section is contrasting against the Humility flow — splitting it would undercut the comparison.
4. **L362 final paragraph** was rewritten to remove both performative and cliche problems. The closing sentence `Your feedback is what keeps Phase 2 grounded in how guilds actually operate.` is a direct call-to-action tail. A strict reviewer could still read it as a closure signal.
5. **"Source of truth" replacement at L109** used "operational record" to avoid the cliche while keeping the engineering meaning. If "record" and "state" read as too similar in context (the next sentence uses "state"), a reviewer may request further differentiation.
