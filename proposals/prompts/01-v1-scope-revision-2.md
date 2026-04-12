# Proposal revision prompt — second pass, scope cuts

## Hard rules (read these first)

**YOU are the proposal-revision agent. YOU do the revision yourself.
Do not launch, spawn, dispatch, or report on any other agent.**
There are no subprocesses. There is no orchestrator.

Your deliverable is an updated `proposals/01-v1-scope.md`.

- **DO** read the current `proposals/01-v1-scope.md` in full
- **DO** read `risk/01-scope.md` (the MEDIUM report you're
  addressing), `risk/01-audit.md` (LOW, stays LOW — don't break it),
  `risk/01-shortcut.md` (LOW, stays LOW — don't break it),
  `DECISIONS.md`, `AGENTS.md`, `NOTES.md`
- **DO** write the revised proposal back to
  `proposals/01-v1-scope.md` using your Write tool (overwriting)
- **DO NOT** modify any other file
- **DO NOT** rewrite sections that are not in the findings list
- **DO NOT** introduce new design decisions
- **DO NOT** expand scope
- **DO NOT** launch subprocesses
- **DO NOT** print progress commentary

## Context

The rev1 proposal passed audit (LOW) and shortcut (LOW) risk gates
but scope returned MEDIUM again. Scope's concern is that the proposal
is over-engineered for Humility's scale (84 members, 0 populated
chapters, 3 test tickets in 4 years). The revision added the
hardening audit wanted (DB-level triggers, full redaction, image
bounds, lockdown-on-create), which tightened the security model
correctly but made scope's concern sharper: more invariants + more
infrastructure = more budget spent on machinery the small server
won't exercise.

Scope laid out two paths to LOW. This revision takes **Path A**:
surgical cuts to durability machinery, keeping all four subsystems.
Path B (defer tickets) was considered and rejected — cutting a whole
subsystem is a bigger scope change than the findings require and
would leave ticketsbot.net dangling longer.

Your job: apply the specific cuts below and nothing else. The
four-subsystem shape stays. Option C sequencing stays. The mutation
safety wrapper stays. Application flow, ticket flow, activity flow,
chapter flow all stay. What goes is the **durability machinery**
underneath them.

## Mandatory cuts (these gate scope LOW)

### C1 — Schema trim (Scope Finding 1)

Apply these schema simplifications in §3:

**C1.1** — Merge `application_messages` and `ticket_messages` into a
single `thread_messages` table. The merged schema:
```sql
CREATE TABLE app.thread_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_kind TEXT NOT NULL CHECK (parent_kind IN ('application', 'ticket')),
    application_id UUID REFERENCES app.applications(id) ON DELETE RESTRICT,
    ticket_id UUID REFERENCES app.tickets(id) ON DELETE RESTRICT,
    discord_message_id BIGINT NOT NULL UNIQUE,
    discord_channel_id BIGINT NOT NULL,
    author_discord_user_id BIGINT,
    content TEXT,
    embeds_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    components_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    referenced_discord_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    ingest_source app.message_ingest_source NOT NULL,
    CHECK (
        (parent_kind = 'application' AND application_id IS NOT NULL AND ticket_id IS NULL)
        OR
        (parent_kind = 'ticket' AND ticket_id IS NOT NULL AND application_id IS NULL)
    )
);
```

Index on `(parent_kind, application_id, created_at)` and `(parent_kind, ticket_id, created_at)` as partial indexes. Update §4 and §5 to reference the merged table.

**C1.2** — Drop `application_form_versions` as a separate table. Move
`schema_json`, `schema_hash`, and `schema_yaml` inline onto
`applications` as columns captured at submission time. Drop the
versioned-form CRUD flow; forms are still YAML in repo and still
published via `discord_cli.py forms publish`, but the publish step
updates an `application_forms` row's current snapshot fields (not a
new version row). This removes the version table entirely. The
`applications` row still preserves forever-history because the
snapshot is stored on the row itself. When a chapter actually revises
a form later, we can add a separate versions table via additive
migration — that's a v2 concern.

Update §3 to remove the `application_form_versions` table and
restructure `application_forms` to hold current snapshot inline.
Update §4 to reflect the simpler publish flow.

**C1.3** — Drop the `chapter_channel_kind` ENUM. Replace with
`kind TEXT NOT NULL` on `chapter_channels`. The enum was 13 values
and adding a new channel kind currently requires a migration; a TEXT
column with a code-level constants module is cheaper for this
scale. Update §3.

**C1.4** — Collapse `provisioning_runs` and `provisioning_steps` into
a single `provisioning_runs` table with a JSONB `steps_json` column
that holds the step log as an array of step objects. This removes one
table and simplifies the resume model (see C2 below which removes
the need for resumable step tracking anyway). Update §3. Document the
`steps_json` shape as `[{step_order, step_key, status, target_kind,
target_discord_id, started_at, finished_at, error_text}, ...]`.

### C2 — Provisioning is a linear runner, not a saga (Scope Finding 2)

Rewrite §7 to remove the saga state machine. The new model:

- `discord_cli.py chapters create --spec <path>` writes a
  `provisioning_runs` row with `status = planned` and the full spec
- The daemon's admin loop picks up `planned` runs and executes them
  in a single Python function that walks the step list top-to-bottom
- Each step goes through the existing mutation safety wrapper, which
  writes an `audit_events` row
- The `provisioning_runs.steps_json` array is updated as steps
  complete
- On failure, the run is marked `failed` with the failing step key;
  **manual cleanup + re-run is the recovery path**, not automatic
  resume. This matches Humility's provisioning frequency (0-3 times
  in v1's lifetime)
- `--dry-run` still populates `steps_json` with the full plan and
  returns without mutating Discord

Drop the `provisioning_run_state` and `provisioning_step_state`
enums — replace with a simpler `status TEXT CHECK (...)` on the run
row. Step-level state lives in `steps_json` and is informational, not
transactional.

Update §13 rollback plan to reflect this: "preserve, not delete"
remains the rule; the cleanup path on a failed run is the same
archival flow that a fully-provisioned chapter would use if
retired, applied to whatever partial state exists.

### C3 — Append-only enforcement is code-level, not DB-level (Scope Finding 5)

Downgrade the append-only requirement in §3 and §8 from
DB-level (triggers or role grants) to **code-level with CI
enforcement**.

- `audit_events`, `application_status_history`, and the
  `steps_json` column on `provisioning_runs` are append-only by
  convention
- CI runs a grep check that rejects any module outside a whitelisted
  writer module from importing or emitting `UPDATE`/`DELETE` SQL
  against those tables
- The writer module for each append-only table is the single entry
  point, and it only exposes `append_*` methods
- This is the same pattern already used in §8 for mutation primitive
  gating

Remove all DDL references to `BEFORE UPDATE OR DELETE` triggers and
to dedicated Postgres roles. Update §9 to note that the daemon uses
the Supabase service key for all writes, and the single-writer
architecture is the reason append-only can be enforced in code
rather than at the DB layer. If a second writer ever appears (v2
web dashboard, etc.), promote append-only to DB triggers at that
time — this is the same "reconsider RLS if a second client appears"
posture §9 already documents.

The rationale must explicitly name the single-writer, service-key
posture as the reason code-level enforcement is sufficient. Do not
remove the CI grep check — that's load-bearing.

### C4 — Drop ticket-to-application promotion (Scope Finding 4)

- Remove `promoted` from `app.ticket_state` ENUM in §3
- Drop `promoted_to_application_id` FK column from
  `app.tickets` in §3
- Remove the ticket-to-application promotion flow from §5
- Add one sentence to §14 anti-scope: "ticket-to-application
  promotion: data-loss scenario is recoverable with a copy-paste
  at Humility's historical volume (3 test tickets in 4 years);
  revisit if real ticket volume materializes"

### C5 — Cut staging Railway service (Scope Finding 6)

Update §11 and §12 Phase 0:

- **Keep**: staging Discord guild (already exists, `Humility Beta`,
  `1492663622458151003`). This is non-negotiable because
  Discord role/thread/overwrite behavior cannot be mocked reliably.
- **Keep**: staging Supabase project on free tier (auto-pause
  accepted; re-wake on demand is acceptable friction)
- **Cut**: staging Railway service. During development, the daemon
  runs locally (user's WSL host) against the staging guild and
  staging Supabase. Production is the only Railway deployment.
- Update §12 Phase 0 to drop the "staging-parity checklist" gate.
  Phase 0 definition of done becomes: production Railway service
  boots, connects to production Discord + production Supabase,
  runs migrations, `/daemon-ping` works in production Humility.
  Local development targets the staging guild.

Update §17 Cost model accordingly. Remove the staging Railway
line. The net cost range goes down.

## Mandatory one-sentence clarifications (audit findings, apply alongside)

Audit's 7 findings are all LOW and non-gating, but three are trivial
one-sentence edits that tighten the document. Apply these in the
same revision:

### A1 — Redaction covers provisioning runs (Audit Finding 2)

Extend the §8 redaction paragraph: the redaction filter explicitly
covers `provisioning_runs.steps_json` (including its nested
`error_text` fields) alongside `audit_events` and structured logs.
All JSONB columns that store mutation payloads go through the same
filter.

### A2 — Dry-run is enforced at the mutation wrapper (Audit Finding 3)

Add one sentence to §7: the daemon's admin loop short-circuits
runs with `dry_run = TRUE` through a planning-only path that
populates `steps_json` with the full plan, marks the run
`completed`, and performs no Discord mutation. The mutation wrapper
itself rejects calls originating from a run row with
`dry_run = TRUE` — the flag is a boundary, not a hint.

### A3 — JSONB column size cap (Audit Finding 4)

Add one sentence to §8: the redaction/serialization wrapper
enforces a 64 KB upper bound per JSONB/TEXT payload column on
`audit_events`, `provisioning_runs.steps_json`,
`activity_imports.raw_vision_response_json`, and
`activity_imports.raw_llm_response_json`, with truncation-with-marker
on overflow. Forever-retention cost-and-bloat hygiene.

### A4 — Phase 2b is its own proposal + risk cycle (Audit Finding 5)

Add one sentence to §12 Phase 2b: if phase 2a's measured accuracy
misses the calibrated gate and phase 2b is triggered, phase 2b goes
through its own proposal and risk cycle before shipping. This
defers the hallucination-validator architecture to a dedicated
gate rather than hand-waving it.

### A5 — Discord CDN URL expiry is a known gap (Audit Finding 6)

Add one sentence to §4 or §5: v1 stores Discord CDN URLs for
attachment references in `thread_messages.attachments_json`,
accepts the Discord CDN URL expiry limitation as a known gap, and
documents it as v2 work (rehost to Supabase Storage). OCR imports
are not affected because the image bytes and Vision response are
already persisted in `activity_imports`.

## Scope findings you do NOT need to address

These are LOW-severity observations in the scope report that don't
gate LOW and don't require edits:

- **Scope Finding 3**: Tickets subsystem is premature but accepted.
  No change needed.
- **Scope Finding 7**: Schema commits (this is handled by Finding 1
  schema trim above).
- **Scope Finding 8**: Critical-path sequencing is correct. Accept.
- **Scope Finding 9**: Cost model calibration. Partially addressed by
  C5 (cutting staging Railway line). Rest can be accepted.
- **Scope Finding 10**: Gold-set construction labor. Add a note in
  §12 Phase 2a that building the 20-screenshot gold set is the
  user's own time, and the phase does not ship until the measurement
  pass has run — but do not move it to a separate phase.

## Audit findings you do NOT need to address

- **Audit Finding 1**: now moot because append-only goes code-level
  per C3. Remove the prior "trigger or role" language from §3/§8 and
  replace with the code-level story from C3.
- **Audit Finding 7**: operational reminder, no proposal edit.

## Shortcut findings

Shortcut returned LOW; leave shortcut-related text alone except
where C1 C2 C3 C4 require schema changes that shortcut already
accepted.

## Revision hygiene

- Preserve section numbering and ordering. Do not reorder.
- The revised proposal will be **shorter** than rev1, not longer —
  you are removing tables, enums, states, and a subsystem flow.
  Target: 7000–8500 words (rev1 was ~9000).
- Update the executive summary (§1) only where scope actually
  changed: append-only moved to code, provisioning is linear,
  schema trimmed, ticket-to-application promotion dropped. The
  architecture bullet list stays the same.
- Do not rewrite sections that aren't in the findings list.
- Keep the existing DDL style (enums, UUID PKs, TIMESTAMPTZ, etc.)
  for the surviving tables. The DDL changes are surgical: delete
  dropped tables, edit modified tables, leave the rest alone.

## Output

Write the revised proposal to `proposals/01-v1-scope.md`,
overwriting. Do not touch any other file. When done, stop.
