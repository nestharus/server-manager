# Audit risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (audit)

## Verdict

**LOW**

The revised proposal concretely addresses every MEDIUM-severity
finding from the prior audit pass — DB-enforced append-only on
`audit_events` / `application_status_history` /
`application_form_versions` / `provisioning_steps`, explicit
parameterized-query requirement, image-upload format/size/pixel
bounds with per-chapter quotas and a Gemini circuit breaker,
lockdown-on-create overwrites for new channels, `HUMILITY_ENV` plus
baked-in guild-ID mapping as a startup gate, a redaction filter for
audit-event payloads and structured logs, CI-enforced mutation-
wrapper exclusivity, and a one-liner stating that no Discord user
IDs accompany image bytes to Vision/Gemini. The bounded mutation
model, resumable provisioning saga, append-only audit trail, Vendor
isolation of OCR to activity imports, Captcha.bot-verified role
mutation, and non-destructive archival all survive scrutiny. The
residual findings below are small gaps in text or implementation
hints — none involves a concrete exploit path or data-loss scenario
on the live Humility guild, and none requires proposal changes that
meaningfully alter the design. A handful of one-sentence
clarifications would tighten the document further; none are gating.

## Findings

### Finding 1 — Append-only enforcement option collides with the service-key auth model

- **Severity**: LOW
- **Section of proposal**: §3 (table notes), §8 (shared
  infrastructure), §9 (RLS / service credential)
- **Description**: §3 and §8 offer two interchangeable options for
  enforcing append-only on `audit_events` and friends: a
  `BEFORE UPDATE OR DELETE` trigger that raises, or "a dedicated
  daemon Postgres role that has `SELECT` + `INSERT` only on those
  tables." The second option is not actually compatible with §9's
  "the daemon uses a service credential" posture — the Supabase
  service key bypasses RLS and has broad rights, so granting a
  narrower role to the daemon means the daemon cannot use the
  service key for those writes, and must hold two connections with
  different credentials, or switch to a non-service Postgres role
  entirely. The proposal doesn't say which is intended.
- **Why it matters**: If an implementer reads "or a daemon DB role"
  as satisfied by the service key (since it *is* a role), the
  append-only guarantee silently collapses into a convention, which
  is exactly what the previous audit flagged as the hazard. The
  correct path is trigger-based enforcement, because triggers fire
  regardless of connection role; role-grant-based enforcement
  requires an actual privilege drop, which the service-key path
  does not provide.
- **Recommendation**: In §3 and §8, collapse the two options into
  one: require the `BEFORE UPDATE OR DELETE` trigger. If the
  dedicated-role path is kept as an alternative, state explicitly
  that the daemon must connect with that role (not the service key)
  for writes touching those tables, and that the service key is
  only used where broad access is actually needed. One sentence in
  §8 or a tweak to the table notes is sufficient.

### Finding 2 — Redaction filter scope excludes `provisioning_steps` payload columns

- **Severity**: LOW
- **Section of proposal**: §8 (redaction filter), §3
  (`provisioning_steps`)
- **Description**: §8 says "audit-event payloads and structured
  logs go through a redaction filter before persistence or stdout
  emission," and scopes the filter to `audit_events` plus stdout.
  `provisioning_steps.request_json`, `response_json`, and
  `error_text` are not mentioned. These columns store the concrete
  Discord REST request and response bodies for chapter provisioning
  — the exact surface most likely to carry bearer headers if any
  code path ever passes a raw request envelope into the step logger.
- **Why it matters**: Forever-retention (D4) combined with
  administrator-permission on a live guild makes a token leaking
  into `provisioning_steps` the same blast-radius as a leak into
  `audit_events`. This is a belt-and-suspenders concern — the
  mutation wrapper already requires sanitized plan objects — but
  the redaction sentence is load-bearing and should cover every
  JSONB column that stores mutation payloads, not just the audit
  table.
- **Recommendation**: Extend the §8 redaction paragraph to
  explicitly include `provisioning_steps.request_json`,
  `response_json`, and `error_text` alongside `audit_events` and
  structured logs. One sentence.

### Finding 3 — Dry-run provisioning has a column but no described enforcement

- **Severity**: LOW
- **Section of proposal**: §7 (operator flow), §3
  (`provisioning_runs.dry_run`)
- **Description**: §7 describes the dry-run flow as
  `discord_cli.py chapters create --spec <path> --dry-run` followed
  by operator review, and §3 stores a `dry_run BOOLEAN` on
  `provisioning_runs`. What's missing is a statement that the
  daemon's admin loop inspects `dry_run` and routes the run through
  a planning-only path that writes `provisioning_steps` rows without
  invoking the mutation wrapper against Discord. Absent that, a
  coding bug where the admin loop ignores the flag would silently
  execute a planned-only run against the live guild. This is the
  "wrong env by accident" pattern the previous finding on
  `HUMILITY_ENV` already addressed for cross-environment safety,
  but not for intra-environment dry-run vs execute.
- **Why it matters**: Chapter provisioning is the highest-blast-
  radius workflow in v1, per §7. A silent dry-run bypass on the
  live guild creates the full set of roles, category, channels, and
  panels for a chapter the operator had not yet approved. Rollback
  is §13's non-destructive-archive path, which is correct but not
  free.
- **Recommendation**: Add one sentence to §7: the daemon's admin
  loop short-circuits `dry_run = TRUE` runs through a planning-only
  path that populates `provisioning_steps` with the full plan,
  marks the run `completed`, and performs no Discord mutation. The
  mutation wrapper itself rejects calls originating from a run row
  with `dry_run = TRUE`. This turns the flag into a boundary rather
  than a hint.

### Finding 4 — Unbounded JSONB payloads in audit and provisioning tables

- **Severity**: LOW
- **Section of proposal**: §3 (`audit_events`, `provisioning_steps`,
  `activity_imports`)
- **Description**: `audit_events.request_payload`, `before_state`,
  `after_state`, `error_text`, `provisioning_steps.request_json` /
  `response_json`, and `activity_imports.raw_vision_response_json` /
  `raw_llm_response_json` are all JSONB/TEXT without a declared
  upper bound. A bug that stuffs a full guild snapshot or a
  megabyte-scale Vision response into one of these columns — once —
  is permanently logged under the forever-retention rule. It is not
  a leak path, but it is a quiet cost-and-table-bloat path on a
  Supabase Pro plan.
- **Why it matters**: Not a security or privacy concern on its
  own; it's a data-integrity concern in the sense that unbounded
  rows can push the DB into a state where routine operations slow
  down or cost models break. On an append-only table with no
  deletes, there is no cleanup path.
- **Recommendation**: Add a sentence to §3 or §8 committing to an
  upper bound on payload/state column sizes (e.g., 64 KB per
  column, with truncation-with-marker on overflow), enforced at the
  wrapper-serialization layer. This is the same layer that already
  does redaction, so it's one additional check in the same place.

### Finding 5 — Phase 2b validator architecture is underspecified for a subsystem that can silently rewrite activity history

- **Severity**: LOW (accept as written with one tweak)
- **Section of proposal**: §6 (phase 2a/b note), §12 (phase 2b),
  §15 (risk 1)
- **Description**: Phase 2a uses Google Cloud Vision
  `DOCUMENT_TEXT_DETECTION`, which is a token/bounding-box OCR
  rather than a generative model — there is effectively no
  hallucinated-row hazard in phase 2a because tokens derive from
  pixels. Phase 2b adds Gemini 3 Flash Preview as a fallback "plus
  a second-pass validator" and only ships if phase 2a misses its
  accuracy gate. The validator's shape is not described: is it a
  deterministic classical-OCR cross-check on the same image, a
  second LLM pass, or a row-by-row confidence reconciler? The
  hallucination risk of a vision LLM silently awarding points to a
  nonexistent player is real and is called out in §15 risk 1, but
  the mitigation is "validator" with no architecture.
- **Why it matters**: If phase 2b ships as currently described,
  the validator design is load-bearing for the audit-risk claim
  that hallucinated rows cannot land in `activity_log`. The phase
  2a design is genuinely safe (Vision does not hallucinate rows in
  this sense, and the correction flow supersedes rather than
  mutates). Phase 2b is the one that needs an architecture for its
  validator, not just a name.
- **Recommendation**: Accept as written for v1 phase 2a. Add a
  sentence to §6 or §12 that phase 2b is a separate
  proposal-and-risk cycle before shipping, specifically because the
  validator architecture needs its own audit pass. This defers the
  concern rather than hand-waving it, and matches the project's
  phase-gate workflow in AGENTS.md.

### Finding 6 — Discord CDN URL expiry affects long-term reference integrity of activity imports and transcripts

- **Severity**: LOW
- **Section of proposal**: §3 (`activity_imports.original_image_url`,
  `ticket_messages.attachments_json`,
  `application_messages.attachments_json`,
  `activity_log.source_image_url`)
- **Description**: Discord began expiring CDN attachment URLs in
  2023–2024 via signed query parameters. The proposal stores URLs
  for screenshots and for message attachments but does not describe
  rehosting to durable storage. For OCR imports the primary data
  survives because `image_sha256`, `raw_vision_response_json`, and
  `activity_log` rows are persisted in Postgres, so the `url` is a
  convenience link rather than the system of record. For ticket and
  application attachments, the transcript row stores only the URL
  and metadata, so linked content becomes unreachable over time.
- **Why it matters**: This is a data-integrity and forever-retention
  issue rather than a security issue. The retention decision D4 was
  "keep everything forever," which URL-only attachment storage
  silently violates. It is audit-adjacent because ticket/application
  threads are the primary after-the-fact record of a membership or
  support decision.
- **Recommendation**: Add a sentence to §4/§5 or §8 stating that v1
  accepts the Discord-CDN-URL durability limitation for attachment
  references and documents it as a known gap to be addressed in a
  later phase (e.g., rehosting to Supabase Storage). That turns a
  silent failure mode into a tracked one. No code change required
  for v1 if the gap is explicitly accepted.

### Finding 7 — Role-hierarchy preflight is described but the current live-server state (server-manager at position 1) will fail every run

- **Severity**: LOW (operational, not design)
- **Section of proposal**: §7 step 1 (preflight), §16 (open
  questions), cross-referenced with `NOTES.md`
- **Description**: §7 preflight verifies that the daemon role
  outranks Captcha.bot and every chapter role it will create. Per
  `NOTES.md`, the `server-manager` role currently sits at position
  1 (near the bottom of the hierarchy), and §16 already asks
  whether it needs to be raised. This is correctly identified in
  the proposal as an open question for the hookpoint phase, so the
  proposal is not wrong — it's a reminder that phase 0 must include
  a tier-3 role-position adjustment on the live guild before any
  chapter provisioning can succeed. That adjustment is itself a
  live-server mutation gated by the Live Server Principle.
- **Why it matters**: Not an audit hit on the proposal. It's a
  reminder that the proposal's preflight will abort loudly, which
  is the correct behavior, and that a tier-3 manual step stands in
  front of any phase 4 success.
- **Recommendation**: Accept as written. No change to the proposal
  needed. The first-deploy checklist in §11 should probably grow
  one line about verifying role position before phase 4, but that's
  a checklist tweak, not a design edit.

## Overall assessment

The proposal's revision closes every MEDIUM finding from the prior
pass with specific, enforceable text: DB-level append-only
enforcement, parameterized queries, image-upload bounds with
circuit breakers, lockdown-on-create channel overwrites, startup-
time environment-guild matching, redaction filters, and CI-enforced
mutation primitive imports. The bounded mutation wrapper remains
the central control and is now backed by a mechanical boundary, not
a convention.

The seven residual findings are uniformly LOW severity. Three (1,
2, 3) are one-sentence clarifications that would turn already-
described controls into unambiguous commitments. Two (4, 6) are
forever-retention hygiene reminders that don't invalidate the
design. One (5) defers an underspecified subsystem to its own
future risk cycle, which matches the phase-gate workflow and does
not block v1. One (7) is an operational note that the proposal's
preflight correctly catches.

None of the findings describes a concrete exploit, privacy leak,
data-loss path, or unsafe assumption against the live Humility
guild given the proposal's stated controls. None requires a
rewrite, a section deletion, or a design change. The proposal is
safe to proceed to the hookpoint phase once the peer audits (scope,
shortcut) also return LOW.

## What a LOW verdict requires

The verdict is LOW because every material concern either (a) has
no realistic attack or data-loss path given the proposal's stated
controls, or (b) is addressed by a control already described in
the proposal text. Findings 1–4 would each improve the proposal's
clarity with a single sentence, but none of them is a prerequisite
for implementation: the underlying controls exist, and the
ambiguities are interpretive rather than structural. Findings 5
and 6 are explicitly phase-scoped or accepted-as-known. Finding 7
is operational guidance, not a design flaw.

If the author wants to tighten the document before the hookpoint
phase, applying findings 1–4 as one-sentence edits in §3, §7, and
§8 is a ~10-minute pass and would remove the last interpretive
ambiguity from the append-only, dry-run, and redaction controls.
None of those edits affects scope, schema, or sequencing.
