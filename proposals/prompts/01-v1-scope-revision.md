# Proposal revision prompt — apply risk assessment findings

## Hard rules (read these first)

**YOU are the proposal-revision agent. YOU do the revision yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is an updated `proposals/01-v1-scope.md`.

- **DO** read the current `proposals/01-v1-scope.md` in full
- **DO** read `risk/01-audit.md`, `risk/01-scope.md`,
  `risk/01-shortcut.md` — these are your directives
- **DO** read `DECISIONS.md` (especially D6 and D7),
  `research/02-humility-needs.md`, `AGENTS.md`, `NOTES.md` as needed
- **DO** write the revised proposal back to
  `proposals/01-v1-scope.md` using your Write tool (overwriting)
- **DO NOT** modify any other file
- **DO NOT** rewrite sections that the risk reports accepted
- **DO NOT** introduce new design decisions beyond what the risk
  reports require
- **DO NOT** expand scope — all risk findings ask for either
  cuts, clarifications, or small additions, never new features
- **DO NOT** launch subprocesses
- **DO NOT** print progress commentary or describe the revised file
  when you're done

Your job is surgical edits to the proposal text that bring all three
risk verdicts to LOW. You do not get to revisit the research or
decisions.

## Three risk reports, one revision

Three separate `claude-opus` risk assessors returned **MEDIUM** on
the v0 proposal. The findings overlap in two places (both agree to
drop `moderator` ticket type, both agree to treat OCR thresholds as
starter values pinned to a calibration gate). Apply every finding
listed below. The numbers below renumber across all three reports
for clarity.

### Must-address findings (these gate the LOW verdict)

Each one has a specific recommended fix from the risk report. Apply
the fix. Do not invent your own version.

**R1 — Audit F1: Secret redaction in logs and audit events**
(MEDIUM, §8/§10)

Add a paragraph to §8 (Shared infrastructure) or §10 (Observability)
stating: audit event payloads and structured logs go through a
redaction filter that strips known secret env-var names,
`authorization` headers, and anything matching a bot-token / API-key
shape. The mutation wrapper accepts only sanitized plan objects, not
raw HTTP bodies. Exceptions raised during mutations are scrubbed
before hitting `error_text` or stdout.

**R2 — Audit F2: DB-level append-only enforcement**
(MEDIUM, §3/§8)

Require that `audit_events`, `application_status_history`,
`application_form_versions`, and `provisioning_steps` enforce
append-only at the database layer via either a
`BEFORE UPDATE OR DELETE` trigger that raises, or a dedicated
Postgres role used by the daemon that is `GRANT INSERT, SELECT` only
on these tables. Update §3 to reference this enforcement in the DDL
commentary for the affected tables, and §8 to name the requirement.

**R3 — Audit F4: User-uploaded image bounds, rate limits, circuit
breaker** (MEDIUM, §6)

Add to §6 (Activity tracking subsystem):
- Format allowlist: PNG, JPEG, WebP only. Reject everything else.
- Maximum decoded pixel area: 25 megapixels (approx 5000×5000).
- Maximum attachment size: 8 MB.
- Per-chapter per-day quota on imports.
- Circuit breaker on Gemini fallback usage per hour.
- Preprocessing runs in a bounded-memory worker and catches decoder
  exceptions.
- Note that the daemon is single-process, so CPU-bound preprocessing
  on a pathological image can stall the gateway heartbeat — explicit
  bound on preprocessing wall time per image.

**R4 — Audit F5: Lockdown-on-create pattern for provisioning channels**
(MEDIUM, §7 step 4)

Update §7 step 4 to require: every channel is created with a minimal
lockdown overwrite in the same REST call (deny `VIEW_CHANNEL` to
`@everyone` and to all server roles until the real overwrites are
written in step 5). Alternatively, channels are created under a
locked-down staging category first and only moved into their final
category after overwrites are finalized. Explicitly state that no
application panel, queue message, or seed content is posted to a
channel until its final overwrites are in place.

**R5 — Scope F1 / Shortcut F1: Drop `moderator` and `chapter_incident`
ticket types for v1** (MEDIUM)

Remove both types from v1.
- Update `app.ticket_type` enum in §3 to only include
  `server_support` and `chapter_support`.
- Update §5 to describe only those two types.
- Remove the Trial Mod read-only overwrite logic from §5 — it
  becomes v2 work when real moderators exist.
- The `CHECK` constraint on `tickets` (§3) simplifies accordingly.
- Update §14 (anti-scope) to explicitly list `moderator` and
  `chapter_incident` ticket types as v1-deferred, with the reason:
  no active moderators or chapter incident handlers exist, and
  building plumbing for empty handler roles is a deferred half-
  solution.
- Leave a note that the enum can be extended with a normal additive
  migration when those roles become real.

**R6 — Scope F2: Cut live gateway transcript streaming**
(MEDIUM, §5, §3)

For v1, transcripts are captured by a single fetch over thread
history on close (plus `manual_backfill`). No gateway create/edit/
delete subscription for tracked ticket or application threads.
- Update §5 transcript persistence to reflect this.
- Update §3 `app.message_ingest_source` ENUM to only include
  `close_reconcile` and `manual_backfill` for v1 (the other values
  are v2 additions).
- Update §4 application thread message persistence to use the same
  close-time fetch pattern.
- Leave `ticket_messages` and `application_messages` schemas as-is;
  they support both patterns.

**R7 — Scope F3: Make phase 1 chapter bootstrap explicit**
(MEDIUM, §12)

Add to §12 Phase 0 (foundations) deliverables: a documented "manual
chapter bootstrap" task — a script or checklist that hand-provisions
one test chapter (roles, category, channels, rows in Postgres,
published form) so phases 1–3 can run against a real chapter before
phase 4 automates provisioning. This bootstrap is deliberately
manual so phase 4 can validate against a real workload. Add one
paragraph making the bootstrap task definition of done.

Update Phase 1 (applications) dependency-in note to reference the
bootstrap task as the upstream unblocker.

**R8 — Shortcut F2 / Scope F6: OCR thresholds as starter values,
phase 2 exit gate** (MEDIUM, §6, §11, §12)

Rewrite §6 to describe the threshold *structure* (median row
confidence + unmatched-rate + duplicate-name check + score-parse
rate) while keeping 0.85/0.70/10%/80% as **starter values pending
measurement, not design commitments**. Add a Phase 2 exit gate in
§12: thresholds are calibrated against the gold set described in §11
before activity tracking ships. If the gold set shows the starters
are wrong, the thresholds get adjusted before phase 2 is declared
done. The thresholds live in code (not DB rows), so calibration is
a code change, not a migration.

**R9 — Shortcut F3: Drop `chapters.settings_json`**
(LOW but easy, §3)

Remove the `settings_json` column from `app.chapters`. Do not replace
it with anything. If a concrete per-chapter setting is needed later,
add an explicit column via additive migration.

### Should-address findings (low-severity clarifications)

These are each a sentence or two of text. Apply them inline during
the revision.

**R10 — Audit F3: SQL parameterization posture**
Add one sentence to §3 or §9: all DB access goes through a
parameterized interface (asyncpg or SQLAlchemy Core, to be decided
at implementation time). No f-string SQL. No dynamic identifier
quoting by hand. Schema and table names are compile-time constants.

**R11 — Audit F6: Env validation at startup**
Add to §9 Deployment: the daemon refuses to start unless the
configured `DISCORD_GUILD_ID` matches an explicit `HUMILITY_ENV`
value (`production` or `staging`) and a hardcoded mapping of
env→guild ID baked into the image. A mismatch aborts startup with
a loud log.

**R12 — Audit F8: Mutation wrapper as architectural boundary**
Add one sentence to §8: Discord mutation primitives are imported
only inside the mutation wrapper module; all other daemon code
imports the wrapper. A CI grep check enforces that no other file
imports `discord.Guild.create_role`, `create_text_channel`,
`edit_role_positions`, or similar direct mutation methods.

**R13 — Scope F4 / Scope F5: Staging Supabase and staging parity**
Fix §17 Cost model:
- Add staging Railway line (~$5/month).
- Either budget staging Supabase Pro ($25) OR document an explicit
  "on-demand staging refresh" workflow that accepts auto-pause on
  free tier. Pick the on-demand approach for MVP; it's cheaper and
  the one-person-plus-agent workflow tolerates the friction.
- Update total ranges to reflect the revised costs.

Add to §12 Phase 0: a "staging parity" checklist that documents
the bootstrap of the staging Discord guild using the manual chapter
bootstrap task. Staging is its own first workload for the manual
bootstrap process.

**R14 — Scope F6 (continued): Phase 2 split into 2a + 2b**
Update §12 Phase 2 (activity tracking) to split into:
- **Phase 2a**: Vision-only ingestion + confidence-based
  accept/flag/review + manual correction + flags. No Gemini
  fallback. Gold-set measurement runs here.
- **Phase 2b**: Add Gemini fallback + second-pass validator, ONLY
  IF phase 2a's measured accuracy misses the calibrated gate.
Mark 2b as conditional. The schema already supports both since
`fallback_ocr_engine` and `raw_llm_response_json` are nullable.

**R15 — Scope F7: Captcha.bot role hierarchy preflight**
Add to §7 Chapter provisioning preflight: the daemon verifies that
its own role position is above both Captcha.bot's managed role and
every chapter role it will create. Add to §4 Applications approval
flow: the daemon verifies that the applicant has cleared whatever
Captcha.bot state Humility uses (the verified role). If not, the
approval fails cleanly with a clear error rather than placing an
unverified user in a chapter.

**R16 — Scope F8: Drop multi-modal form wizard for v1**
v1 supports single-modal forms only. If a chapter authors a YAML
form that exceeds five components at publish time, the publish step
fails with a clear error and refuses to store the version. Update
§4 form rendering strategy to remove the wizard description.
`application_forms` schema does not change.

**R17 — Scope F9: Simplify activity rule evaluation**
Keep the `activity_rules` schema as designed (it costs nothing).
Update §6 to ship rule evaluation with only two knobs in v1:
`threshold_points` and a combined "consecutive days window" that
uses `window_days == minimum_breach_days` and `require_consecutive
= true`. The `comparison_operator` enum defaults to `lt`. These are
hardcoded v1 defaults; the DB columns remain for v2 expansion.

**R18 — Shortcut F4: Define `activity_flags.details_json` shape**
Add to §6 (rule evaluation output): `details_json` carries
`{"breached_days": [ISO dates...], "points_per_day": {date: points},
"rule_snapshot": {threshold, window, operator, ...}}` — all fields
required for dispute reproduction from the row alone.

**R19 — Shortcut F5: Pin form publish trigger**
Add one sentence to §4: publishing is an explicit
`discord_cli.py forms publish` command that reads the YAML,
computes the schema hash, and writes a new
`application_form_versions` row if the hash is new. Daemon startup
logs a warning if any `application_forms` row's `current_version_number`
does not match the hash of its YAML file on disk — this is a drift
alarm, not an automatic republish.

**R20 — Shortcut F6: Configuration surface map**
Add a short "Configuration surface map" section (new subsection in
§8 or §10). One table with three columns:

| Config kind | Storage | Editor |
|---|---|---|
| Application forms | YAML in-repo, DB snapshot on publish | `discord_cli.py forms publish` |
| Activity rules | DB rows | Officer slash commands |
| Chapter member roster | DB rows | Officer slash commands + auto-upsert on approval |
| Application blacklist | DB rows | Officer slash commands |
| Chapter registry | DB rows | `discord_cli.py chapters create` |
| Runtime secrets / env | Railway env vars | Railway dashboard |
| Panel messages | Discord state, provisioned by daemon | Provisioning runs only |

**R21 — Shortcut F7: Pre-research claim helper — accept**
No change required. The proposal already flags it in §16 open
questions. Leave it.

**R22 — Shortcut F8: Audit event type taxonomy note**
Add one sentence to §3 (in the `audit_events` description): the
`event_type`, `target_kind`, and `target_ref` fields are
deliberately `TEXT` rather than enums because the audit event
taxonomy is an open set; the concrete list of event type strings
lives in a constants module in code and every emitter imports from
that module. No schema change.

**R23 — Shortcut F9: RLS v2 note**
Add one sentence to §9: if a second DB client ever appears (web
dashboard, read-only officer UI, etc.), row-level security must be
reconsidered. v1 is single-client so schema isolation + network
privacy is the correct posture.

## Findings you do NOT need to address

- **Audit F7** (PII flow): accepted as written. Optionally add one
  sentence to §6 confirming no Discord user IDs or internal member
  identifiers are passed in Vision/Gemini request envelopes.
- **Shortcut F10** (saga rollback is principled, not shortcut):
  accepted.

## Revision hygiene

- Preserve the existing section numbering — do not renumber or
  reorder sections.
- Keep the executive summary brief and update it only where scope
  actually changed (drop of moderator/incident ticket types is the
  one material scope change).
- Do not rewrite the schema DDL wholesale. Apply surgical edits
  where §3 needs them:
  - Enum changes (R5, R6)
  - Remove `chapters.settings_json` (R9)
  - Define `activity_flags.details_json` shape (R18)
  - Append-only commentary and enforcement (R2)
- The revised proposal should end up slightly shorter than v0, not
  longer, because you are dropping features (moderator ticket type,
  gateway streaming, multi-modal wizard) and adding only short
  paragraphs.
- Target length: 5000–8500 words. (v0 was ~8000; the revision can
  land slightly under.)

## Output

Write the revised proposal to `proposals/01-v1-scope.md`,
overwriting. Do not touch any other file. When done, stop.
