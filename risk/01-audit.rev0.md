# Audit risk assessment — proposals/01-v1-scope.md

Date: 2026-04-11
Assessor: claude-opus (audit)

## Verdict

**MEDIUM**

Six contained findings need proposal-level fixes before implementation,
but the overall design is on the right side of every material axis:
credentials are env-only, OCR vendors are isolated to activity
imports, provisioning is resumable and non-destructive, the mutation
wrapper is explicitly required, and OCR hallucination has a two-pass
validator. The MEDIUM verdict is driven by **things the proposal does
not say** more than by things it says wrong: (a) log/audit-event
secret redaction is not promised, (b) `audit_events` append-only is
a convention, not a DB constraint, (c) SQL-parameterization is
unstated, (d) user-uploaded image bounds are unstated, (e) a small
permission race exists between channel creation and overwrite
application during provisioning, and (f) staging-vs-prod separation is
environmental, not code-enforced. Each fix is a paragraph of text in
the proposal, not a design change. None of them force a rewrite.

## Findings

### Finding 1 — Audit-event and structured-log redaction is not described

- **Severity**: MEDIUM
- **Section of proposal**: §10 (Observability), §3 (`audit_events`),
  §8 (mutation wrapper)
- **Description**: §10 specifies structured JSON logs with
  correlation IDs, Discord user IDs, subsystem names, guild ID, and
  object IDs, but never promises that bot tokens, Supabase service
  keys, Vision keys, or Gemini keys are redacted from log events,
  alert payloads, exception tracebacks, and `audit_events.request_payload` /
  `before_state` / `after_state` / `error_text`. The mutation wrapper
  in §8 stores "the intended change payload" in a `planned` audit row;
  if that payload ever contains a header dict or an HTTP request
  envelope, a token can land in Postgres and in Railway's log stream.
- **Why it matters**: Audit events are designed to be durable forever
  (§3 + D4). A single bad log line bakes a secret into append-only
  history. Railway logs are accessible to anyone with project
  access; Supabase service-key access is effectively full admin on
  the DB. The blast radius of a token in one audit row is the entire
  bot and the entire DB, with no easy scrubbing path given the
  forever-retention rule.
- **Recommendation**: Add a paragraph to §8 or §10: audit event
  payloads and structured logs MUST go through a redaction filter
  that strips known secret env-var names, `authorization` headers,
  and anything matching a bot-token / API-key shape. The wrapper
  should accept only sanitized plan objects, not raw HTTP bodies.
  Exceptions raised during mutations must be scrubbed before hitting
  `error_text` or stdout.

### Finding 2 — `audit_events` append-only is convention, not enforced

- **Severity**: MEDIUM
- **Section of proposal**: §3 (`audit_events`), §8 (shared
  infrastructure)
- **Description**: The proposal calls `audit_events` an "append-only
  history table" but the schema has no mechanism preventing UPDATE or
  DELETE. The daemon uses `SUPABASE_SERVICE_KEY`, which bypasses RLS,
  so any code path (or any operator with that key) can rewrite audit
  history. Same comment applies to `application_status_history` and
  `provisioning_steps`, which are also described as append-only.
- **Why it matters**: The bot holds Administrator on a live guild.
  The audit trail is the primary after-the-fact control on a bounded
  mutation bug or a malicious-insider scenario. If it is silently
  mutable, the control is load-bearing only when nothing is wrong,
  which is exactly when it is not needed.
- **Recommendation**: In §3 and §8, require that `audit_events`,
  `application_status_history`, `application_form_versions`, and
  `provisioning_steps` enforce append-only at the database layer.
  Concrete mechanisms (one or both): a `BEFORE UPDATE OR DELETE`
  trigger that raises, or a dedicated Postgres role used by the
  daemon that is `GRANT INSERT, SELECT` only on these tables. Either
  is a few lines of migration; not a design change.

### Finding 3 — SQL-injection posture is unstated

- **Severity**: LOW
- **Section of proposal**: §3 (Data model), everywhere DB writes are
  implied
- **Description**: The proposal describes rich schemas, JSONB
  payloads, and free-text fields (application answers, ticket
  subjects, decision reasons, chapter slugs, OCR evidence strings,
  in-game names, blacklist reasons) but never states that all writes
  go through parameterized queries / a typed DB client and that no
  user-controlled text is concatenated into SQL. Given the pre-
  research `daemon/db.py` existed in a different (SQLite) shape, it
  is worth being explicit so the rewrite does not inherit ad-hoc
  string building.
- **Why it matters**: Chapter slug and in-game name both touch
  `UNIQUE` indexes and dynamic query paths. A string-concatenation
  bug on any of these fields lets an applicant inject SQL through a
  modal. The service key means the resulting blast is full DB.
- **Recommendation**: Add one sentence to §3 or §9: all DB access
  goes through a parameterized interface (asyncpg / SQLAlchemy
  Core). No f-string SQL. No dynamic identifier quoting by hand.
  Schema and table names are compile-time constants in application
  code.

### Finding 4 — User-uploaded image bounds and per-user rate limits are unstated

- **Severity**: MEDIUM
- **Section of proposal**: §6 (Activity tracking subsystem)
- **Description**: `/activity upload image:<attachment>` accepts an
  attachment; the daemon runs preprocessing (contrast, upscale,
  deskew), hashes the bytes, hits Google Vision, and may escalate to
  Gemini. The proposal does not describe a maximum file size,
  maximum decoded dimensions, format allowlist, per-user per-day
  quota, or a kill switch if a single user triggers Gemini fallback
  repeatedly. A malicious or buggy officer client could upload a
  20,000×20,000 PNG, a decompression-bomb ZIP-smuggled image, or a
  tight loop of low-confidence images that drives the pipeline into
  repeated Gemini calls.
- **Why it matters**: Three distinct failure modes:
  (a) preprocessing libraries (Pillow) have historical parser CVEs
      on malformed inputs, especially when the daemon runs as root
      or without resource caps;
  (b) OCR cost blows up — a user flooding Gemini fallbacks is cheap
      for them but billable to the owner;
  (c) the daemon is single-process on Railway; a CPU-bound preprocess
      on a pathological image stalls gateway heartbeats and trips the
      Docker `HEALTHCHECK`, causing a restart loop that looks like an
      outage to applicants and tickets.
- **Recommendation**: Add to §6: reject non-PNG/non-JPEG/non-WebP
  attachments; cap decoded pixel area (e.g., 25 megapixels) and file
  size (e.g., 8 MB); per-chapter per-day quota on imports; a circuit
  breaker on Gemini fallback usage per hour. Preprocessing runs in a
  bounded-memory worker and catches decoder exceptions. None of this
  is novel, it just needs to be in the proposal so implementation
  does not forget it.

### Finding 5 — Provisioning has a permission race window between channel creation and overwrite application

- **Severity**: MEDIUM
- **Section of proposal**: §7 (Chapter provisioning), step 4→5
- **Description**: §7 step 4 creates channels, step 5 applies channel-
  level overwrites. The proposal explicitly says "Do not rely on
  category inheritance for mission-critical policy" — good, but the
  consequence is that between "channel created" and "overwrites
  applied," the channel has whatever permissions Discord gives a
  freshly-created child: either category-inherited, or default
  `@everyone`-visible if created at guild root. For a chapter with
  sensitive queue channels (`incidents`, officer-only surfaces),
  that window can expose pre-populated data or panels to users who
  should not see them, and if a provisioning step fails mid-run, the
  channel stays in that wrong state until resume completes.
- **Why it matters**: An incidents or officer-lobby channel briefly
  public is a real privacy leak if any content lands in it during
  the window. The saga resume path makes this worse: a failed run
  can leave orphaned half-provisioned channels with non-final
  overwrites sitting around until an operator resumes. §13 says
  orphans are intentionally preserved.
- **Recommendation**: Add to §7 step 4: every channel is created
  with a minimal lockdown overwrite in the same REST call (deny
  `VIEW_CHANNEL` to `@everyone` and to all server roles until the
  real overwrites are written in step 5). Alternatively, create
  channels as children of a locked-down staging category first and
  only move them into their final category after overwrites are
  finalized. State explicitly that no application panel, queue
  message, or seed content is posted to a channel until its final
  overwrites are in place.

### Finding 6 — Staging vs production separation is environmental, not enforced in code

- **Severity**: LOW
- **Section of proposal**: §9 (Deployment), §11 (Testing)
- **Description**: §9 lists required env vars (`DISCORD_GUILD_ID`,
  `SUPABASE_DB_URL`, etc.) and §11 requires a separate staging
  guild + staging Supabase project + staging Railway service. But
  nothing in the daemon prevents a developer from running locally
  with a `.env` that mixes staging keys with a production
  `DISCORD_GUILD_ID`, or a CI run that points staging Supabase at
  the production guild. The failure mode is "I meant to test this
  but I hit prod."
- **Why it matters**: Given Administrator permissions and the live-
  server principle from `AGENTS.md`, a "wrong env by accident" bug
  is a full tier-3 mutation on the real guild — the exact class of
  event the live-server principle exists to prevent.
- **Recommendation**: Add to §9: the daemon refuses to start unless
  the configured `DISCORD_GUILD_ID` matches an explicit
  `HUMILITY_ENV` value (`production` or `staging`) and a hardcoded
  mapping of env→guild ID. Production guild ID is baked into the
  image. Staging guild ID, once it exists, is also baked in. A
  mismatch aborts startup with a loud log. This is a five-line
  check, not a design change.

### Finding 7 — PII flow to third parties is scoped correctly, note for completeness

- **Severity**: LOW (accept as written)
- **Section of proposal**: §2, §6, §9
- **Description**: Vision and Gemini receive screenshots containing
  in-game player names (and potentially nothing else identifying,
  since these are game-UI captures). Gemini is explicitly paid-tier
  per D6, so inputs are not used for training. Google Cloud Vision
  stores request content per its standard terms; no user Discord
  identifiers are sent along with the image in the OCR path because
  the roster mapping happens inside the daemon after OCR returns.
  OCR is not invoked for applications, tickets, or transcripts.
- **Why it matters**: The design already isolates PII flow to the
  smallest defensible surface. This finding exists to document that
  the audit-side review considered it.
- **Recommendation**: Accept as written. Optionally add one sentence
  to §6 confirming that no Discord user IDs or internal member
  identifiers are passed in the Vision/Gemini request envelopes —
  only the image bytes and a generic prompt. This makes future PII
  review trivial.

### Finding 8 — Bounded mutation wrapper enforcement is cultural, not architectural

- **Severity**: LOW (accept as written with one tweak)
- **Section of proposal**: §8 (Shared infrastructure)
- **Description**: §8 says every tier-3 mutation goes through the
  safety wrapper and lists forbidden helpers ("add role X to
  everyone missing it," "sync every channel"). This is exactly the
  right rule, but the proposal gives no way to prevent a future
  code path from calling `guild.edit_role_positions(...)` or
  `channel.edit(...)` directly around the wrapper. It is a
  convention, not a boundary.
- **Why it matters**: The bot holds Administrator; the live-server
  principle in `AGENTS.md` calls this out as the central risk. A
  single bypass during implementation silently disables the audit
  trail for that mutation. This is LOW rather than MEDIUM because
  the wrapper is at least described, required, and auditable in PR
  review.
- **Recommendation**: Add one sentence to §8: Discord mutation
  primitives are imported only inside the wrapper module; all other
  daemon code imports the wrapper. A simple grep in CI enforces that
  no other file imports `discord.Guild.create_role`,
  `create_text_channel`, `edit_role_positions`, or similar. That
  turns convention into a mechanical check.

## Overall assessment

The proposal's explicit controls — mutation wrapper, audit trail,
resumable saga, OCR two-pass validator, vendor isolation, forever-
retention via soft delete, env-only secrets, separate staging —
cover the main audit surface. None of the findings above invalidate
those controls. Findings 1, 2, 4, and 5 are the ones that raise the
verdict to MEDIUM: they are concrete paths (secret in an audit row,
silently-mutable audit row, malicious image, public window on a
newly-created private channel) with concrete blast radius on the
live Humility guild. Findings 3, 6, 7, 8 are either LOW by severity
or accept-as-written with a clarifying sentence.

None of the findings require re-architecture. All of them are
proposal edits measured in sentences or a single migration, and can
be addressed in one revise-and-re-risk pass. The proposal's shape,
subsystem split, and mutation model remain sound.

## What a LOW verdict requires

To move this to LOW, the revised proposal needs to address at least
findings 1, 2, 4, and 5 directly in text:

1. An explicit secret-redaction requirement on logs and audit events.
2. DB-level append-only enforcement on `audit_events`,
   `application_status_history`, `application_form_versions`, and
   `provisioning_steps` (trigger or role-level grant).
3. Explicit user-upload bounds (format, size, dimensions, per-user/
   per-chapter rate, Gemini-fallback circuit breaker) in §6.
4. Lockdown-on-create or staging-category-then-move pattern in §7 so
   no window exists where a partially-provisioned channel is
   visible.

Findings 3, 6, 8 can land as one-sentence clarifications in the same
revision and do not individually gate LOW. Finding 7 is already
accepted.
