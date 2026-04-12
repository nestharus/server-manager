# Humility Discord Daemon v1 Scope Proposal

Date: 2026-04-11

## 1. Executive summary

Humility needs one durable in-house system to replace two dying vendor
surfaces and one daily manual workflow: Gather for chapter applications,
ticketsbot.net/tickets.bot for support queues, and spreadsheet-driven
activity tracking for game screenshots. It is one always-on Discord
daemon on Railway with Supabase Postgres as the system of record, plus
the existing `discord_cli.py` retained as a sibling inspection and admin
tool.

The proposed v1 delivers four subsystems on one shared substrate:

- Applications: per-chapter forms, review queue, claim-based handling,
  interview and waitlist states, durable review history, and role
  mutation on approval.
- Tickets: two ticket types, shared claim semantics, private threads,
  durable transcripts, and clean closure/archive behavior.
- Chapter provisioning: one-command chapter creation from a structured
  chapter spec, with resumable execution, bounded mutations, and full
  audit logging.
- Activity tracking: screenshot upload, Google Cloud Vision
  `DOCUMENT_TEXT_DETECTION` as the primary OCR path, roster mapping, and
  rules-based flagging, with Gemini 3 Flash Preview reserved as a
  conditional fallback if phase 2a misses its accuracy gate.

State lives in Supabase Postgres, not SQLite. There are no compatibility
shims. The daemon is the mutation engine, the CLI stays separate, and
lasting workflow history is duplicated into Postgres rather than left
only in Discord.

Application forms are YAML-authored in-repo and materialized into
database snapshots on publish so Humility gets both reviewable source
control and durable historical rendering.

The core design choice throughout this proposal is to optimize for
durable operations rather than shortcut shipping. That means explicit
state machines, append-only history tables, resumable provisioning,
bounded mutation helpers, and OCR acceptance thresholds that prefer
manual review over silently writing wrong rows. `moderator` and
`chapter_incident` ticket types are deferred to a later additive
migration when Humility has real handler roles for them.

## 2. High-level architecture

```text
Discord Members / Officers / Staff
        |
        | slash commands, buttons, modals, thread messages, attachments
        v
Discord Gateway + REST API
        |
        v
Railway Service: Humility Daemon (discord.py, scheduler, job runner)
        |
        | 1. durable state, queues, audit trail
        v
Supabase Postgres
        |
        | 2. OCR only for activity imports
        +---------------------> Google Cloud Vision
        |                           |
        |                           | low-confidence / ambiguous imports
        |                           v
        +---------------------> Gemini 3 Flash Preview
        |
        | 3. logs / health
        v
Railway log stream + container healthcheck

Local/Admin Surface:
  discord_cli.py --------------> Supabase Postgres (read-mostly, plus
                                 provisioning run requests and admin queries)
```

The daemon is the only always-on process. It owns interactions,
background jobs, and resumable admin work such as chapter provisioning.

Supabase Postgres is the system of record. Discord IDs are treated as
external references, not as durable workflow state. If the Railway
container restarts, no in-flight ticket, application, OCR import, or
provisioning run is lost because every meaningful transition is written
to Postgres before or immediately after the Discord mutation.

Google Cloud Vision and, if phase 2b is needed, Gemini are
activity-tracking dependencies only. They do not participate in
applications, tickets, or provisioning. That boundary matters: if OCR
vendors fail, only activity imports back up. The rest of the daemon
keeps working.

`discord_cli.py` remains separate and mostly read-only. Its main write
surface in v1 is submitting provisioning requests that the daemon then
executes.


## 3. Data model

This schema assumes a dedicated `app` schema inside Supabase Postgres
and `pgcrypto` for UUID generation. Discord snowflakes are stored as
`BIGINT`. Internal workflow rows use UUID primary keys. Timestamps are
always `TIMESTAMPTZ`.

### DDL prelude

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS app;

CREATE TYPE app.application_state AS ENUM (
    'submitted',
    'claimed',
    'interview',
    'waitlist',
    'approved',
    'denied',
    'withdrawn'
);

CREATE TYPE app.ticket_type AS ENUM (
    'server_support',
    'chapter_support'
);

CREATE TYPE app.ticket_state AS ENUM (
    'open',
    'claimed',
    'closed',
    'promoted'
);

CREATE TYPE app.chapter_channel_kind AS ENUM (
    'category',
    'events',
    'guides',
    'lobby',
    'guild_lobby',
    'officer_lobby',
    'applications_queue',
    'tickets_queue',
    'activity_inbox',
    'activity_flags',
    'voice_create_lobby',
    'voice_create_guild_lobby',
    'voice_guild_war'
);

CREATE TYPE app.message_ingest_source AS ENUM (
    'close_reconcile',
    'manual_backfill'
);

CREATE TYPE app.activity_import_state AS ENUM (
    'received',
    'vision_parsed',
    'llm_parsed',
    'needs_review',
    'accepted',
    'rejected',
    'failed'
);

CREATE TYPE app.activity_flag_state AS ENUM (
    'open',
    'acknowledged',
    'resolved',
    'dismissed'
);

CREATE TYPE app.audit_phase AS ENUM (
    'planned',
    'attempted',
    'succeeded',
    'failed',
    'rolled_back'
);

CREATE TYPE app.provision_run_state AS ENUM (
    'planned',
    'running',
    'failed',
    'completed',
    'rolled_back'
);

CREATE TYPE app.provision_step_state AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'rolled_back',
    'skipped'
);
```

### `chapters`

Purpose: one row per live or archived chapter.

```sql
CREATE TABLE app.chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    game TEXT NOT NULL,
    description TEXT,
    created_by_discord_user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    archived_by_discord_user_id BIGINT
);

CREATE INDEX idx_chapters_active ON app.chapters (slug)
WHERE archived_at IS NULL;
```

Nullable: `description` is optional freeform operator context.
`archived_at` and `archived_by_discord_user_id` are null until the
chapter is retired. Soft delete column: `archived_at`.

### `chapter_roles`

Purpose: store the six Discord role bindings for one chapter.

```sql
CREATE TABLE app.chapter_roles (
    chapter_id UUID PRIMARY KEY REFERENCES app.chapters(id) ON DELETE RESTRICT,
    officer_role_id BIGINT NOT NULL UNIQUE,
    member_role_id BIGINT NOT NULL UNIQUE,
    guild_war_role_id BIGINT NOT NULL UNIQUE,
    applicant_role_id BIGINT NOT NULL UNIQUE,
    chapter_role_id BIGINT NOT NULL UNIQUE,
    public_role_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Nullable: none. Each role binding must exist for a provisioned chapter.
No soft delete column here; archival is driven from `chapters`.

### `chapter_channels`

Purpose: one row per provisioned channel or category bound to a chapter.

```sql
CREATE TABLE app.chapter_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    channel_kind app.chapter_channel_kind NOT NULL,
    discord_channel_id BIGINT NOT NULL UNIQUE,
    discord_parent_channel_id BIGINT,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (chapter_id, channel_kind)
);

CREATE INDEX idx_chapter_channels_active ON app.chapter_channels (chapter_id, channel_kind)
WHERE archived_at IS NULL;
```

Nullable: `discord_parent_channel_id` is null for categories and top
level objects. `archived_at` is null until the channel binding is
retired. Soft delete column: `archived_at`.

### `chapter_members`

Purpose: chapter roster and membership history, including in-game name.

```sql
CREATE TABLE app.chapter_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    discord_user_id BIGINT NOT NULL,
    in_game_name TEXT,
    membership_state TEXT NOT NULL CHECK (
        membership_state IN ('applicant', 'member', 'officer', 'former_member', 'removed')
    ),
    source_application_id UUID,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at TIMESTAMPTZ,
    notes TEXT,
    UNIQUE (chapter_id, discord_user_id, joined_at)
);

CREATE UNIQUE INDEX uq_chapter_members_active
ON app.chapter_members (chapter_id, discord_user_id)
WHERE left_at IS NULL;

CREATE INDEX idx_chapter_members_active_name
ON app.chapter_members (chapter_id, in_game_name)
WHERE left_at IS NULL;
```

Nullable: `in_game_name` is nullable because not every legacy member or
ticket requester will have a known game identity at creation time.
`source_application_id` is nullable for manually-added rosters.
`left_at` is null while membership is active. `notes` is optional.
There is no hard delete. Historical rows close by setting `left_at`.

### `application_forms`

Purpose: current form metadata per chapter, sourced from in-repo YAML.

```sql
CREATE TABLE app.application_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL UNIQUE REFERENCES app.chapters(id) ON DELETE RESTRICT,
    form_key TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    current_version_number INTEGER NOT NULL CHECK (current_version_number >= 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (chapter_id, form_key)
);
```

Nullable: `description` is optional. `archived_at` is null while the
form is active. Soft delete column: `archived_at`.

### `application_form_versions`

Purpose: immutable snapshots of form schemas so old submissions always
render against the original questions.

```sql
CREATE TABLE app.application_form_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_form_id UUID NOT NULL REFERENCES app.application_forms(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    schema_json JSONB NOT NULL,
    schema_hash TEXT NOT NULL,
    yaml_source_text TEXT NOT NULL,
    published_by_discord_user_id BIGINT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (application_form_id, version_number),
    UNIQUE (application_form_id, schema_hash)
);
```

Nullable: none. Every stored version must be complete and immutable.
`application_form_versions` is append-only by requirement: v1 enforces
that at the database layer with either a `BEFORE UPDATE OR DELETE`
trigger that raises or a dedicated daemon DB role that has `SELECT` +
`INSERT` only on this table.

### `applications`

Purpose: one durable submission row per application.

```sql
CREATE TABLE app.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    application_form_id UUID NOT NULL REFERENCES app.application_forms(id) ON DELETE RESTRICT,
    application_form_version_id UUID NOT NULL REFERENCES app.application_form_versions(id) ON DELETE RESTRICT,
    applicant_discord_user_id BIGINT NOT NULL,
    applicant_in_game_name TEXT,
    answers_json JSONB NOT NULL,
    status app.application_state NOT NULL DEFAULT 'submitted',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_by_discord_user_id BIGINT,
    claimed_at TIMESTAMPTZ,
    interview_started_at TIMESTAMPTZ,
    waitlisted_at TIMESTAMPTZ,
    decided_by_discord_user_id BIGINT,
    decided_at TIMESTAMPTZ,
    decision_reason TEXT,
    denial_blacklist_requested BOOLEAN NOT NULL DEFAULT FALSE,
    review_channel_id BIGINT NOT NULL,
    review_message_id BIGINT NOT NULL UNIQUE,
    review_thread_id BIGINT NOT NULL UNIQUE,
    archived_at TIMESTAMPTZ
);

CREATE INDEX idx_applications_chapter_status
ON app.applications (chapter_id, status, submitted_at DESC);

CREATE INDEX idx_applications_applicant
ON app.applications (applicant_discord_user_id, submitted_at DESC);

CREATE UNIQUE INDEX uq_open_application_per_user_per_chapter
ON app.applications (chapter_id, applicant_discord_user_id)
WHERE archived_at IS NULL
  AND status IN ('submitted', 'claimed', 'interview', 'waitlist');
```

Nullable: `applicant_in_game_name` is nullable because not every form
must ask it. Claim, interview, waitlist, and decision columns are null
until those transitions happen. `decision_reason` is null until a final
decision. `archived_at` is null until the review thread is closed out of
active views. Soft delete column: `archived_at`.

### `application_status_history`

Purpose: append-only record of every application transition.

```sql
CREATE TABLE app.application_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES app.applications(id) ON DELETE RESTRICT,
    from_status app.application_state,
    to_status app.application_state NOT NULL,
    actor_discord_user_id BIGINT,
    reason TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_application_status_history_app
ON app.application_status_history (application_id, created_at);
```

Nullable: `from_status` is null for the first creation event.
`actor_discord_user_id` is nullable for system-generated transitions
such as automated archival. `reason` is optional per transition.
`application_status_history` is append-only by requirement and must be
enforced at the database layer, not just by daemon convention.

### `application_messages`

Purpose: transcript of application review thread messages.

```sql
CREATE TABLE app.application_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES app.applications(id) ON DELETE RESTRICT,
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
    ingest_source app.message_ingest_source NOT NULL
);

CREATE INDEX idx_application_messages_app
ON app.application_messages (application_id, created_at);
```

Nullable: `author_discord_user_id` is nullable for system/deleted
messages. `content` is nullable because attachment-only messages exist.
`referenced_discord_message_id` is nullable for non-replies. `edited_at`
and `deleted_at` are null unless those events occur. Soft delete marker:
`deleted_at`.

### `application_blacklist`

Purpose: per-chapter blocklist for applicants.

```sql
CREATE TABLE app.application_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    discord_user_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    added_by_discord_user_id BIGINT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_by_discord_user_id BIGINT,
    removed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_application_blacklist_active
ON app.application_blacklist (chapter_id, discord_user_id)
WHERE removed_at IS NULL;
```

Nullable: `removed_by_discord_user_id` and `removed_at` are null until
the blacklist entry is lifted. Soft delete column: `removed_at`.

### `tickets`

Purpose: one durable row per ticket across the two v1 ticket types.

```sql
CREATE TABLE app.tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_type app.ticket_type NOT NULL,
    chapter_id UUID REFERENCES app.chapters(id) ON DELETE RESTRICT,
    requester_discord_user_id BIGINT NOT NULL,
    subject TEXT,
    initial_description TEXT,
    handler_role_discord_id BIGINT NOT NULL,
    watcher_role_discord_id BIGINT,
    status app.ticket_state NOT NULL DEFAULT 'open',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_by_discord_user_id BIGINT,
    claimed_at TIMESTAMPTZ,
    closed_by_discord_user_id BIGINT,
    closed_at TIMESTAMPTZ,
    close_reason TEXT,
    requester_left_guild_at TIMESTAMPTZ,
    queue_channel_id BIGINT NOT NULL,
    queue_message_id BIGINT NOT NULL UNIQUE,
    thread_id BIGINT NOT NULL UNIQUE,
    promoted_to_application_id UUID REFERENCES app.applications(id) ON DELETE SET NULL,
    archived_at TIMESTAMPTZ,
    CHECK (
        (ticket_type IN ('server_support') AND chapter_id IS NULL)
        OR
        (ticket_type IN ('chapter_support') AND chapter_id IS NOT NULL)
    )
);

CREATE INDEX idx_tickets_route_status
ON app.tickets (ticket_type, chapter_id, status, opened_at DESC);

CREATE INDEX idx_tickets_requester
ON app.tickets (requester_discord_user_id, opened_at DESC);

CREATE UNIQUE INDEX uq_open_ticket_per_route
ON app.tickets (
    requester_discord_user_id,
    ticket_type,
    COALESCE(chapter_id, '00000000-0000-0000-0000-000000000000'::uuid)
)
WHERE archived_at IS NULL
  AND status IN ('open', 'claimed');
```

Nullable: `chapter_id` is nullable for server-wide ticket types only.
`subject` and `initial_description` are optional because panel-created
tickets may begin with a minimal prompt. Claim and close columns are
null until those actions happen. `watcher_role_discord_id` is nullable
for routes without a separate watcher role. `requester_left_guild_at` is
null unless the requester leaves. `archived_at` is null until the ticket
is out of active views. Soft delete column: `archived_at`.

### `ticket_messages`

Purpose: transcript of all ticket thread messages.

```sql
CREATE TABLE app.ticket_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES app.tickets(id) ON DELETE RESTRICT,
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
    ingest_source app.message_ingest_source NOT NULL
);

CREATE INDEX idx_ticket_messages_ticket
ON app.ticket_messages (ticket_id, created_at);
```

Nullable: same rationale as `application_messages`. Soft delete marker:
`deleted_at`.

### `activity_rules`

Purpose: per-chapter threshold and window rules for flagging low
activity.

```sql
CREATE TABLE app.activity_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    rule_name TEXT NOT NULL,
    threshold_points INTEGER NOT NULL CHECK (threshold_points >= 0),
    comparison_operator TEXT NOT NULL CHECK (comparison_operator IN ('lt', 'lte')),
    window_days INTEGER NOT NULL CHECK (window_days >= 1),
    minimum_breach_days INTEGER NOT NULL CHECK (minimum_breach_days >= 1),
    require_consecutive BOOLEAN NOT NULL DEFAULT TRUE,
    notify_discord_channel_id BIGINT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_discord_user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at TIMESTAMPTZ,
    UNIQUE (chapter_id, rule_name)
);

CREATE INDEX idx_activity_rules_active
ON app.activity_rules (chapter_id)
WHERE archived_at IS NULL AND enabled = TRUE;
```

Nullable: `archived_at` is null while the rule is active. Soft delete
column: `archived_at`.

### `activity_imports`

Purpose: one OCR ingestion job per uploaded screenshot.

```sql
CREATE TABLE app.activity_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    source_discord_channel_id BIGINT NOT NULL,
    source_discord_message_id BIGINT NOT NULL UNIQUE,
    uploaded_by_discord_user_id BIGINT NOT NULL,
    activity_date DATE NOT NULL,
    original_image_url TEXT NOT NULL,
    image_sha256 TEXT NOT NULL,
    preprocessing_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    primary_ocr_engine TEXT NOT NULL,
    fallback_ocr_engine TEXT,
    import_state app.activity_import_state NOT NULL DEFAULT 'received',
    raw_vision_response_json JSONB,
    raw_llm_response_json JSONB,
    parsing_notes TEXT,
    reviewed_by_discord_user_id BIGINT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_activity_imports_chapter_date
ON app.activity_imports (chapter_id, activity_date DESC);

CREATE INDEX idx_activity_imports_state
ON app.activity_imports (import_state, created_at);
```

Nullable: `fallback_ocr_engine` is null if the LLM path was not used.
Raw response JSON columns are null until that stage executes.
`parsing_notes`, reviewer columns, and `processed_at` are workflow
dependent. No hard delete; rejected imports remain in history.

### `activity_log`

Purpose: one parsed activity row per player line from an accepted or
reviewed import.

```sql
CREATE TABLE app.activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_import_id UUID NOT NULL REFERENCES app.activity_imports(id) ON DELETE RESTRICT,
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    chapter_member_id UUID REFERENCES app.chapter_members(id) ON DELETE SET NULL,
    discord_user_id BIGINT,
    row_number INTEGER NOT NULL CHECK (row_number >= 1),
    extracted_player_name TEXT NOT NULL,
    normalized_player_name TEXT NOT NULL,
    activity_date DATE NOT NULL,
    points INTEGER NOT NULL CHECK (points >= 0),
    row_confidence NUMERIC(5,4) NOT NULL CHECK (row_confidence >= 0 AND row_confidence <= 1),
    evidence_text TEXT NOT NULL,
    evidence_bbox_json JSONB,
    source_image_url TEXT NOT NULL,
    is_corrected BOOLEAN NOT NULL DEFAULT FALSE,
    corrected_by_discord_user_id BIGINT,
    corrected_at TIMESTAMPTZ,
    superseded_by_activity_log_id UUID REFERENCES app.activity_log(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (activity_import_id, row_number)
);

CREATE INDEX idx_activity_log_member_date
ON app.activity_log (chapter_id, discord_user_id, activity_date DESC);

CREATE INDEX idx_activity_log_unmatched
ON app.activity_log (chapter_id, activity_date DESC)
WHERE chapter_member_id IS NULL;
```

Nullable: `chapter_member_id` and `discord_user_id` are nullable for
unmatched players awaiting roster mapping. `evidence_bbox_json` is
nullable because some OCR responses will not preserve useful geometry
after correction. Correction and supersession columns are null until
human review alters a row.

### `activity_flags`

Purpose: durable record of rules-derived low-activity findings.

```sql
CREATE TABLE app.activity_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_rule_id UUID NOT NULL REFERENCES app.activity_rules(id) ON DELETE RESTRICT,
    chapter_id UUID NOT NULL REFERENCES app.chapters(id) ON DELETE RESTRICT,
    chapter_member_id UUID NOT NULL REFERENCES app.chapter_members(id) ON DELETE RESTRICT,
    discord_user_id BIGINT NOT NULL,
    flag_date DATE NOT NULL,
    computed_window_start DATE NOT NULL,
    computed_window_end DATE NOT NULL,
    details_json JSONB NOT NULL,
    status app.activity_flag_state NOT NULL DEFAULT 'open',
    posted_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by_discord_user_id BIGINT,
    UNIQUE (activity_rule_id, chapter_member_id, flag_date)
);

CREATE INDEX idx_activity_flags_open
ON app.activity_flags (chapter_id, status, flag_date DESC);
```

Nullable: `posted_message_id` is null until the notification is posted.
Resolution columns are null until the flag is handled. `details_json`
must be sufficient to reproduce the flag from the row alone and carries
`{"breached_days": [ISO dates...], "points_per_day": {date: points},
"rule_snapshot": {threshold, window, operator, ...}}`.

### `audit_events`

Purpose: durable audit trail for planned and executed mutations and
state transitions.

```sql
CREATE TABLE app.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    phase app.audit_phase NOT NULL,
    actor_discord_user_id BIGINT,
    target_kind TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    before_state JSONB,
    after_state JSONB,
    error_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_events_correlation
ON app.audit_events (correlation_id, created_at);

CREATE INDEX idx_audit_events_target
ON app.audit_events (target_kind, target_ref, created_at DESC);
```

Nullable: `actor_discord_user_id` is nullable for daemon-internal
events. `before_state`, `after_state`, and `error_text` are only
populated when relevant. `audit_events` is append-only by requirement
and must be enforced at the database layer with either a
`BEFORE UPDATE OR DELETE` trigger that raises or a daemon DB role that
has `SELECT` + `INSERT` only on this table. `event_type`,
`target_kind`, and `target_ref` stay `TEXT` because the audit taxonomy
is intentionally open-ended; the concrete event strings live in a code
constants module and every emitter imports from there.

### `provisioning_runs`

Purpose: durable, resumable chapter-provisioning requests.

```sql
CREATE TABLE app.provisioning_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_slug TEXT NOT NULL,
    requested_by_discord_user_id BIGINT NOT NULL,
    spec_json JSONB NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    status app.provision_run_state NOT NULL DEFAULT 'planned',
    failure_summary TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_provisioning_runs_status
ON app.provisioning_runs (status, created_at);
```

Nullable: `failure_summary`, `started_at`, and `finished_at` are
workflow dependent.

### `provisioning_steps`

Purpose: step-by-step execution log for a provisioning run.

```sql
CREATE TABLE app.provisioning_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provisioning_run_id UUID NOT NULL REFERENCES app.provisioning_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL CHECK (step_order >= 1),
    step_key TEXT NOT NULL,
    mutation_kind TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_discord_id BIGINT,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_json JSONB,
    status app.provision_step_state NOT NULL DEFAULT 'pending',
    error_text TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    UNIQUE (provisioning_run_id, step_order),
    UNIQUE (provisioning_run_id, step_key)
);

CREATE INDEX idx_provisioning_steps_status
ON app.provisioning_steps (provisioning_run_id, status, step_order);
```

Nullable: `target_discord_id` is null before a create step succeeds.
`response_json`, `error_text`, and timestamps are workflow dependent.
`provisioning_steps` is append-only by requirement and must be enforced
at the database layer, not left to daemon convention.

All database access in v1 goes through a parameterized interface
(`asyncpg` or SQLAlchemy Core, chosen at implementation time). No
f-string SQL, no hand-built identifier quoting, and schema/table names
are compile-time constants.

## 4. Applications subsystem

Form authoring should be YAML in-repo, not DB-authored. That is the
best fit for Humility’s actual operating model. The owner wants
reviewable, diffable definitions that an agent can update without a
third-party dashboard. The research also showed the prior SaaS path is
exactly the dependency surface that failed. The database still stores
published snapshots because runtime history must not depend on whatever
the repo contains later.

The slash surface is one command: `/apply chapter:<chapter>`. The
chapter option autocompletes from active `chapters` rows where an active
`application_forms` row exists. If the applicant already has an open
application for that chapter, the daemon rejects the command ephemerally
and links the review thread status if the user is allowed to see it.

Blacklist checks happen before any modal is rendered. The daemon
consults `application_blacklist` on the selected chapter. If the user is
actively blacklisted, it returns an ephemeral rejection message and does
not open the form. This avoids leaking question content or creating dead
submissions for known blocked users.

The form rendering strategy uses current Discord modal capabilities
rather than the stale pre-research assumptions. v1 supports single-
modal forms only. At publish time, `discord_cli.py forms publish` reads
the YAML, computes the schema hash, and writes a new
`application_form_versions` row if the hash is new. If the authored form
would require more than five components, publish fails with a clear
error and does not store the version. Daemon startup logs a warning if
any `application_forms.current_version_number` does not match the hash
of its YAML file on disk; that is a drift alarm, not an automatic
republish.

Submission persistence happens before any staff-facing side effect other
than the interaction acknowledgement. The daemon creates the
`applications` row, appends a `submitted` history event, snapshots the
form version, and only then posts the review message into the chapter’s
applications queue.

The review embed shape is:

- Title: `Application #<short-id> · <Chapter Display Name>`
- Fields: applicant mention, applicant Discord ID, submitted time, form
  version number, extracted in-game name if present
- Answer summary: one field per question up to Discord limits, with
  overflow linked to thread seed text
- Footer: current state plus reviewer if claimed

The buttons are `Claim`, `Interview`, `Waitlist`, `Approve`, and
`Deny`. There is no separate “Close” action on applications because
applications end in `approved`, `denied`, or `withdrawn`; closure is a
derived archival step after a terminal state.

Thread creation is immediate after the review message is posted. The
bot creates a private thread off that queue message and seeds it with:
the applicant, all members currently in the chapter’s officer role, and
all members currently in the server-wide `Staff` role. Administrators
retain override access by permission, but the bot still keeps staff
explicitly present because `Staff` is not necessarily `Administrator`.
The seed message inside the thread includes the full rendered answer set
and the form schema version number.

Claim semantics are shared with tickets but the application rules are:

- `submitted -> claimed`: one officer claims the review.
- On claim, non-claimer chapter officers are removed from the private
  thread.
- The applicant and server-wide staff remain.
- The queue embed updates to show the claimer and timestamp.
- A second claim attempt fails cleanly with an ephemeral message.

The application state machine is:

- `submitted -> claimed`
- `claimed -> interview`
- `claimed -> waitlist`
- `claimed -> approved`
- `claimed -> denied`
- `interview -> waitlist`
- `interview -> approved`
- `interview -> denied`
- `waitlist -> claimed`
- `waitlist -> approved`
- `waitlist -> denied`
- `submitted|claimed|interview|waitlist -> withdrawn` by applicant or staff

Interview and waitlist are deliberately different. `interview` means the
application is active and the reviewer is using the private thread to
collect more information. `waitlist` means the application is paused
without further action expected from the applicant right now. Both are
non-terminal. Only `approved`, `denied`, and `withdrawn` are terminal.

Approval performs three classes of work: durable state transition,
Discord role mutation, and closure. The durable update happens first:
the `applications` row moves to `approved`, the history row records the
actor, and an `audit_events` record captures the planned role changes.
Before any role mutation, the daemon verifies that the applicant has
cleared Humility's Captcha.bot verification gate. If the verified role
is missing, approval fails cleanly with a clear error rather than
placing an unverified user into a chapter. The role mutation then adds
the chapter member role and the chapter umbrella role if that role
participates in overwrites, removes the chapter applicant role, and
optionally upserts `chapter_members` using the submitted in-game name.
The bot DMs the applicant, archives and locks the thread, updates the
queue message, and stamps `archived_at`.

Deny requires explicit reason capture. The `Deny` button opens a modal
with a required reason and an optional “add to chapter blacklist” flag.
If the chapter policy says denial does not imply blacklisting, the flag
defaults to off. If enabled, the denial flow appends an
`application_blacklist` row in the same logical transaction boundary as
the denial status write. Then it DMs the applicant, archives the thread,
and marks the queue message accordingly.

Data retention is soft-delete only. Applications are never physically
deleted in v1. Even withdrawn applications remain queryable. Messages in
application threads are persisted into `application_messages` by a
single fetch over thread history when the thread closes, plus
`manual_backfill` for repair or historical imports. v1 does not
subscribe to create/edit/delete gateway events for application threads,
so the applicant/reviewer conversation survives outside Discord without
introducing live transcript-streaming machinery.

Form schema evolution is handled by snapshotting the published schema at
submission time. When a chapter changes its YAML form, the next publish
creates a new `application_form_versions` row and increments
`current_version_number`. Existing applications continue to render using
the schema JSON referenced by their stored `application_form_version_id`.
That avoids the common “old answer keys no longer map to current
question labels” failure mode.

## 5. Tickets subsystem

Tickets use the same thread-and-claim primitives as applications, but
they differ in routing and transcript retention.

The two v1 ticket types are:

- `server_support`: server-wide support questions, routed to `Staff`.
- `chapter_support`: chapter-specific support, routed to that chapter’s
  officer role, with `Staff` retained as watcher/override.

The user-facing surface is both slash and panel-based. `/ticket
type:<type> chapter:<chapter?> subject:<subject?>` is the fallback.
Permanent button panels are the primary UX and are deployed
idempotently into the server support surface and each provisioned
chapter queue.

Claim mechanics are the shared ones from applications, with one extra
rule: watcher-role members stay in the thread after claim. In v1,
claiming a chapter-support ticket narrows chapter-officer participants
down to the claimer while still keeping `Staff` watcher members
present.

Transcript persistence in v1 is close-time and backfill-only. On close,
the daemon fetches the full thread history once and persists it into
`ticket_messages` with `ingest_source = 'close_reconcile'`. A separate
`manual_backfill` path exists for repair or historical import. v1 does
not subscribe to message create/edit/delete gateway events for tracked
ticket threads.

Close flow is explicit. The `Close` button opens a modal for reason and
optional requester DM. The daemon writes `closed` state, appends a
ticket close audit event, persists a final transcript reconciliation,
DMs the requester if possible, updates the queue embed, and archives and
locks the thread. Closed tickets remain queryable forever.

If the requester leaves the server mid-ticket, the ticket does not
break. The daemon marks `requester_left_guild_at`, updates the embed,
and keeps the ticket open for staff handling. The thread becomes
staff-facing only because the requester can no longer participate. Close
or escalation continues normally.

Ticket-to-application promotion is worth supporting because it prevents
staff from forcing users to start over. The flow is:

- A staffer clicks `Promote to Application` in a server-support or
  chapter-support ticket.
- The bot prompts for target chapter.
- It creates a new `applications` row referencing the relevant form
  version, copies the ticket subject/body into an internal note or seed
  message, and sends the requester a modal or DM prompt for the missing
  structured fields.
- The original ticket moves to `promoted`, gets linked to the new
  application, and is archived once the promotion handoff is complete.

This avoids data loss while preserving the application workflow as the
system of record for actual membership decisions.

## 6. Activity tracking subsystem

The primary input surface is a slash command executed in a chapter’s
dedicated activity channel:
`/activity upload image:<attachment> date:<optional>`. If the command is
run inside a chapter activity channel, the chapter is inferred. If run
elsewhere by staff, the chapter becomes a required argument. This keeps
the interaction explicit, supports historical backfill via the `date`
argument, and avoids accidental OCR from random image drops.

Roster setup is ongoing, not one-time. Approved applications should
auto-upsert `chapter_members` with the applicant’s in-game name if the
form captured it. Officers can also manage the roster directly with
commands like `/chapter roster upsert member:@user ign:<name>`. OCR
imports rely on this mapping but do not require it to exist up front;
unmatched rows are stored and resolved later.

Input handling is intentionally bounded before any OCR call. v1 accepts
PNG, JPEG, and WebP only; rejects every other format; caps attachment
size at 8 MB; and rejects images whose decoded pixel area exceeds
25 megapixels. Imports are quota-limited per chapter per day, Gemini
fallback usage has a per-hour circuit breaker, preprocessing runs in a
bounded-memory worker, decoder exceptions are caught and surfaced as
clean import failures, and each image has an explicit preprocessing
wall-time cap because the daemon is single-process and a pathological
CPU-bound image must not stall gateway heartbeats.

The OCR pipeline for v1 phase 2a is:

1. Receive image and create `activity_imports` row in `received` state.
2. Optionally preprocess the image using a chapter-specific crop preset
   if one exists, then normalize contrast, upscale small text when
   useful, and deskew if a strong rotation is detected. Preprocessing
   metadata is stored in `preprocessing_json`.
3. Call Google Cloud Vision `DOCUMENT_TEXT_DETECTION` on the processed
   image.
4. Flatten the Vision response into tokens with text, confidence, and
   bounding boxes. Group tokens into rows by vertical overlap and
   y-centroid proximity using median token height as the tolerance
   anchor.
5. Within each row, sort tokens left-to-right and classify the
   rightmost parseable integer cluster as the score candidate. Treat the
   remaining left-side text as the player-name candidate after stripping
   obvious headers and separators.
6. Score each row using a weighted confidence formula:
   mean token confidence, numeric parse confidence, row-shape quality,
   and roster match confidence. Also compute import-level checks:
   row count, unmatched player rate, duplicate names, and suspicious
   score distribution.
7. Decide among two v1 phase-2a outcomes: accept directly if the
   confidence structure passes, or mark `needs_review` if the import is
   medium-confidence, unmatched-heavy, or structurally ambiguous.
8. Persist accepted rows into `activity_log`, mark the import accepted,
   and queue flag computation.

The acceptance logic should be conservative, but the proposal commits to
the threshold structure rather than treating its first numbers as design
truth. The decision uses median row confidence, unmatched-row rate, a
duplicate-normalized-name check, and score-parse rate. Starter values
are median confidence `0.85` for direct accept, `0.70` as the lower
bound for review, fewer than `10%` unmatched rows, and at least `80%`
of rows with clean integer score parsing. Those are pending
measurement, not fixed design commitments. The thresholds live in code,
not DB rows, so calibration is a normal code change rather than a
migration.

No Discord user IDs or internal member identifiers are sent to Vision or
Gemini request envelopes; only the image bytes and a generic extraction
prompt leave the daemon. Phase 2b adds Gemini 3 Flash Preview fallback
plus a second-pass validator only if phase 2a misses the calibrated
accuracy gate.

The activity rule “DSL” should not be YAML. Officers need to edit
operational thresholds from Discord, not from Git. v1 uses structured DB
rows in `activity_rules`, but rule evaluation ships with only two knobs
live in v1: `threshold_points` and a combined consecutive-days window
where `window_days == minimum_breach_days` and
`require_consecutive = true`. `comparison_operator` defaults to `lt`.
The other columns remain in the schema for later expansion. “Flag
anyone under 50 points for 3 consecutive days” becomes:

- `threshold_points = 50`
- `comparison_operator = 'lt'`
- `window_days = 3`
- `minimum_breach_days = 3`
- `require_consecutive = true`

Flagging output should post into the chapter’s dedicated
`activity_flags` channel, not DMs. That keeps officer review in one
shared place and avoids waking members directly based on possibly wrong
OCR. The flag embed includes the member mention, in-game name, breached
dates, rule name, and link back to the source import thread.

Mis-scanned rows need a correction UI, but the right v1 UI is not a
fancy dashboard. Each import gets a review message with `Accept All`,
`Reject Import`, and `Open Review Thread`. Inside the review thread,
officers use slash commands such as `/activity correct import:<id>
row:<n> member:@user points:<n>` and `/activity map-player import:<id>
row:<n> member:@user`. Corrections create superseding `activity_log`
rows rather than mutating history in place.

When new players appear before they are in the roster, the import still
lands. The row is stored with `chapter_member_id` null. The review
message lists unmatched players separately. Once an officer maps the
player to a Discord member or creates a roster entry, the daemon updates
future matching and recomputes any affected flags.

Historical backfill is supported. Officers can upload old screenshots by
providing `date:` explicitly. The subsystem treats backfill exactly like
current-day imports except that flag computation uses the provided date
range rather than “today.” This is important because v1 should be able
to seed history from pre-daemon screenshots.

## 7. Chapter provisioning subsystem

Chapter provisioning is the highest-blast-radius workflow in scope. It
creates roles, categories, channels, overwrites, form bindings, and
activity rules. Because that payload is too large and too risky for a
Discord modal, the primary trigger should be the CLI, not a slash
command.

The operator flow is:

- Write or generate a chapter spec file containing display name, slug,
  game, initial officers, form definition, and activity rules.
- Run `discord_cli.py chapters create --spec <path> --dry-run`.
- Review the generated step plan.
- Re-run with `--execute` after explicit approval.

The CLI does not perform Discord mutations directly. It writes a
`provisioning_runs` row with `status = planned`, and the daemon’s admin
job loop executes it. This preserves one mutation engine, one audit
trail, and one set of bounded-mutation helpers.

The required inputs are:

- chapter display name
- chapter slug
- game
- initial officer Discord user IDs
- form YAML definition
- one or more activity rules
- optional chapter description

The mutation sequence is:

1. Preflight checks: verify role headroom, category headroom, channel
   headroom, slug uniqueness, that the daemon role is above Captcha.bot's
   managed role, and that it is above every chapter role it will create.
2. Create six chapter-specific roles cloned from the template role
   settings.
3. Create the chapter category.
4. Create template-derived channels plus the chapter queue channels
   `applications`, `tickets`, `activity`, and
   `activity-flags`, each with a minimal lockdown overwrite in the same
   REST call that denies `VIEW_CHANNEL` to `@everyone` and to all server
   roles until final overwrites are applied.
5. Apply channel-level overwrites explicitly to every created channel.
   Do not rely on category inheritance for mission-critical policy.
   No panel message, queue message, or seed content is posted anywhere
   until those final overwrites are in place.
6. Write the `chapters`, `chapter_roles`, and `chapter_channels` rows.
7. Publish the chapter form into `application_forms` and
   `application_form_versions`.
8. Write the chapter’s `activity_rules`.
9. Post the application panel in the chapter applications channel.
10. Mark the provisioning run completed.

Idempotency is handled with a saga-style workflow, not a fake global
transaction. Every step writes a `provisioning_steps` row before and
after attempting the Discord mutation. On retry, completed steps are
reused. If a step fails after a Discord object was created, its resulting
Discord ID is stored in `target_discord_id`, so resume logic can either
rebind to the existing object or continue from the next safe point.

Chapter archival is the inverse flow, but it is intentionally
non-destructive. Archival should:

- mark the chapter row `archived_at`
- archive panel messages
- disable new applications, tickets, and activity imports
- move the category under an archived meta-category or rename/hide it
- set `chapter_channels.archived_at`
- end active rules by setting `archived_at`

Roles and channels should not be hard-deleted automatically in v1.
Humility’s working rule is preserve, not delete.

Role cap and category cap checks happen in preflight. The current server
has enough headroom, but the daemon must fail loudly if a run would
cross Discord’s 250-role or 50-category limit. It should also preflight
total channel count because chapter queues add more than the template
alone.

Provisioning UX should be explicit and inspectable. The CLI prints the
planned steps and current run status. The daemon mirrors progress into
`audit_events` and can optionally post a staff-only progress summary in
`#admin-chat`.

## 8. Shared infrastructure

The claim-visibility helper should be a first-class shared component.
Its interface conceptually takes:

- a queue item type (`application` or `ticket`)
- the requester Discord user ID
- the claimer Discord user ID
- the list of route handlers to remove on claim
- the list of persistent watcher members to keep
- the queue message and thread IDs to update

That helper is responsible for thread membership narrowing, queue embed
update text, and durable audit logging. Applications and tickets should
not duplicate this logic.

Every tier-3 mutation goes through a mutation safety wrapper. The
wrapper pattern is:

1. Build a concrete operation plan with exact target IDs and intended
   sanitized change payload.
2. Write an `audit_events` row with `phase = planned`.
3. Execute one bounded mutation.
4. Write `phase = succeeded` or `phase = failed` with before/after
   snapshots.

This is how the bot stays safe despite holding `Administrator`.
Discord mutation primitives are imported only inside the wrapper module;
all other daemon code imports the wrapper, and CI enforces that no other
file imports direct mutation methods such as
`discord.Guild.create_role`, `create_text_channel`, or
`edit_role_positions`.

The bounded mutation pattern must prohibit “mass update by accident”
helpers. Allowed helpers look like:

- add role X to member Y
- remove role X from member Y
- create one role with spec S
- create one channel with spec S
- edit one thread membership set for thread T

Forbidden helpers in v1 are implicit bulk operations such as “add role X
to everyone missing it” or “sync every channel under this category.”
Bulk work, when truly needed, should be expanded into an explicit list of
bounded steps and logged individually.

Audit-event payloads and structured logs go through a redaction filter
before persistence or stdout emission. The filter strips known secret
env-var names, `authorization` headers, and values matching bot-token or
API-key shapes. The mutation wrapper accepts only sanitized plan
objects, never raw HTTP bodies, and exceptions raised during mutations
are scrubbed before hitting `error_text` or stdout.

Append-only durability is a database requirement, not a code-style
preference. `audit_events`, `application_status_history`,
`application_form_versions`, and `provisioning_steps` are protected at
the database layer by either `BEFORE UPDATE OR DELETE` triggers that
raise or a dedicated daemon Postgres role that has `SELECT` + `INSERT`
only on those tables.

Background jobs stay in-process in v1. The daemon runs a lightweight
scheduler for:

- daily activity flag computation
- retrying failed OCR imports
- expiring abandoned application drafts
- resuming planned provisioning runs

These jobs must be idempotent and catch up on startup by reading
database state.

### Configuration surface map

| Config kind | Storage | Editor |
| --- | --- | --- |
| Application forms | YAML in-repo, DB snapshot on publish | `discord_cli.py forms publish` |
| Activity rules | DB rows | Officer slash commands |
| Chapter member roster | DB rows | Officer slash commands + auto-upsert on approval |
| Application blacklist | DB rows | Officer slash commands |
| Chapter registry | DB rows | `discord_cli.py chapters create` |
| Runtime secrets / env | Railway env vars | Railway dashboard |
| Panel messages | Discord state, provisioned by daemon | Provisioning runs only |

## 9. Deployment

The Docker image should use a slim Python base plus `uv` for dependency
installation. A reasonable sketch is:

- base: `python:3.13-slim`
- install system packages needed by the runtime and image processing
- copy `pyproject.toml` and lock data first for layer caching
- install dependencies with `uv sync --frozen`
- copy repo contents
- run as non-root
- entry point: `uv run python -m daemon`

The Railway service runs a single always-on container in a US West
region close to the owner and Discord’s common US routes. The health
check should be container-local, not an extra HTTP server: the daemon
updates a heartbeat file or timestamp every 30 seconds, and Docker
`HEALTHCHECK` verifies freshness.

Required environment variables are:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID`
- `SUPABASE_DB_URL`
- `SUPABASE_SERVICE_KEY`
- `GOOGLE_CLOUD_VISION_KEY`
- `GEMINI_API_KEY`

Those live in Railway for production and in a local `.env` for admin
CLI use. The repository stores none of them.
The daemon refuses to start unless `DISCORD_GUILD_ID` matches both a
declared `HUMILITY_ENV` value (`production` or `staging`) and a
hardcoded env-to-guild-ID mapping baked into the image. Any mismatch
aborts startup with a loud log.

Supabase should be structured as one production project and one staging
project. v1 does not need multiple logical schemas for product reasons,
but using an `app` schema is still useful to keep bot tables separate
from Supabase defaults. Row-level security is not a meaningful control
plane in this design because the daemon is the only application client
and uses a service credential. The correct safety posture is to keep the
database private and the schema explicit, not to pretend end-user RLS
policies matter for a bot-only backend. If a second DB client ever
appears later (web dashboard, read-only officer UI, or similar), row-
level security must be reconsidered at that point.

Migration tool choice should be Alembic. The app is Python-native,
schema changes are part of the code lifecycle, and the project needs
ordered, reviewable revisions with downgrade stories. Supabase CLI
migrations are viable, but Alembic fits the implementation stack better
and keeps Python-side deployment logic coherent.

The monorepo layout should remain close to the current repo:

- `discord_cli.py` at root
- `daemon/` for the persistent bot
- `forms/` for authored YAML form definitions
- `migrations/` for Alembic revisions
- `research/`, `proposals/`, `risk/` unchanged

The CLI and daemon share library code where useful, but they remain
separate executables with separate responsibilities.

## 10. Observability

Logs should be structured JSON to stdout so Railway can collect them
without extra plumbing. Each log event should include correlation ID,
Discord user ID when applicable, subsystem, guild ID, and object IDs for
applications, tickets, imports, or provisioning runs.

Metrics worth tracking are:

- slash command count and failure rate
- application counts by state
- ticket counts by type and state
- active claimed threads
- OCR import volume
- OCR fallback rate from Vision to Gemini
- OCR confidence distribution
- unmatched roster row rate
- provisioning run duration and failure count
- Supabase connection failure count

Alerting should be minimal but real. The owner should be notified for:

- daemon process repeatedly dying or heartbeat going stale
- inability to reach Supabase for more than a short window
- repeated Google Vision auth/quota failures
- repeated Gemini fallback failures
- provisioning run failures
- OCR backlog age exceeding a threshold

Not every ticket failure should wake the owner at 2am. OCR errors,
application DM failures, or one bad panel deploy should log and mark the
work item failed without crashing the process.

## 11. Testing strategy

Unit tests should focus on pure logic:

- application state transitions
- ticket state transitions
- form version publication
- OCR row grouping and confidence scoring
- activity rule evaluation
- bounded mutation planner validation
- provisioning plan expansion and resume logic

Integration tests need two layers. First, a mocked Discord layer should
exercise command handlers, message ingestion, and audit logging without a
real guild. Second, a real staging Discord guild should exist for
permission, thread, and overwrite behavior that mocks will never model
perfectly. A sandbox category inside live Humility is not a sufficient
replacement because the project’s own policy says visible live-server
mutations require explicit care per action.

Staging should therefore be:

- one separate staging Discord guild
- one staging Supabase project
- one Railway staging service

Phase 0 also includes a staging-parity checklist driven by the same
manual bootstrap path used for the first real chapter. Staging is the
first workload for that checklist: create the staging guild baseline,
hand-provision one test chapter, publish its form, mirror the critical
roles/channels, and confirm Captcha.bot assumptions before later phases
touch production-facing flows.

Manual first-deploy checklist:

- `/daemon-ping` works
- one test chapter can be provisioned in staging
- one test application goes from submit to approve with DM notification
- one OCR screenshot produces accepted rows or review-required rows as
  expected
- one test ticket creates a thread, captures transcript, and closes
- one provisioning rollback or resume scenario works

OCR accuracy needs a real acceptance harness. Build a gold set of
Humility-style screenshots with expected rows and scores. Measure:

- row detection recall
- exact score accuracy
- correct player-name normalization
- unmatched-player rate
- false acceptance rate on ambiguous screenshots

The goal for v1 is not “never ask a human to review.” The goal is “only
accepted rows are trustworthy enough to avoid re-checking everything.”

## 12. Sequencing plan (Option C)

### Phase 0: foundations

Definition of done: Railway daemon boots, connects to Discord, uses
Supabase successfully, migrations run, CI executes, and `/daemon-ping`
works. Phase 0 also includes a documented manual chapter bootstrap task:
a checklist or script that hand-provisions one test chapter with real
roles, category, channels, Postgres rows, and a published form so
phases 1 through 3 run against a real chapter before phase 4 automates
the flow.

Demoable outcome: the owner can invoke `/daemon-ping` in Humility and
see a live response backed by the real deployment stack.

Dependency for next phase: stable deployment, schema, audit trail, and
shared command scaffolding, plus one manually bootstrapped test chapter
and the staging-parity checklist completed against the staging guild.

The manual bootstrap task is done only when one chapter can actually
accept an application, hold a ticket, and receive an activity upload
without any provisioning automation. That chapter is deliberately
hand-built so phase 4 later validates its automation against a known
real workload rather than against an invented spec-only target.

### Phase 1: applications

Definition of done: one working chapter has an active form, `/apply`
submits, review thread is created, claim/interview/waitlist/approve/deny
work, and approval performs the right DM and role mutations.

Demoable outcome: a full end-to-end chapter application from applicant
to approval or denial.

Dependency for next phase: the manual chapter bootstrap path has already
provided the upstream chapter surface, and `chapter_members` upsert path
plus claim helper are now real, which activity tracking can reuse for
roster mapping.

### Phase 2a: activity tracking baseline

Definition of done: officers can upload a screenshot, the daemon runs
Vision OCR, persists accepted rows, posts flags for breached rules, and
supports manual correction/review without any Gemini fallback.

Demoable outcome: one screenshot turns into stored activity rows and, if
thresholds are breached, a visible officer-facing flag message.

Exit gate: thresholds are calibrated against the gold set in §11 before
phase 2a is declared done. If the starter values are wrong, they are
adjusted in code before the phase closes.

Dependency for next phase: none structurally, but the OCR job framework
and audit patterns help ticket transcript and import reconciliation.

### Phase 2b: activity tracking fallback (conditional)

Definition of done: Gemini fallback plus second-pass validation are
added only if phase 2a misses the calibrated accuracy gate from the
gold-set measurement.

Demoable outcome: an ambiguous screenshot that phase 2a could not accept
or review efficiently is recovered by the fallback path with validator
support.

Dependency for next phase: conditional only; phase 3 can proceed
directly if phase 2a already meets the calibrated gate.

### Phase 3: tickets

Definition of done: both v1 ticket types can be opened, claimed,
transcribed, and closed; transcripts persist in Postgres; requester-left
guild cases and promotion-to-application work.

Demoable outcome: a ticket thread is created from a panel button, then
closed with a durable transcript.

Dependency for next phase: shared claim/thread primitives are complete,
which provisioning can reference when creating queue surfaces.

### Phase 4: chapter provisioning automation

Definition of done: a CLI-submitted provisioning spec creates one
chapter end-to-end, including roles, category, channels, form
publication, activity rules, and application panel deployment, with
resume support on failure.

Demoable outcome: a brand-new chapter appears with all operational
surfaces live and bound in Postgres.

Dependency after phase 4: v1 is feature-complete.

## 13. Rollback plan

Phase 0 rollback is mostly redeploying the previous image and, if
necessary, rolling back the last additive migration. The safest schema
policy is additive-first so application-level rollback rarely needs a DB
downgrade.

Phase 1 rollback means redeploying the previous daemon image, disabling
application panel messages, and leaving existing application data intact.
No submissions are deleted.

Phase 2 rollback means stopping new activity imports and redeploying the
previous image. Existing imports and rows remain in the database. If a
bad OCR rule caused noisy flags, flags can be dismissed rather than
deleted.

Phase 3 rollback means disabling ticket panels and redeploying the
previous image. Open ticket threads remain visible to staff, and their
transcripts remain intact.

Phase 4 rollback is the hardest because Discord-visible objects have
been created. The correct rollback is not automatic deletion. It is:

- stop the failed provisioning run
- mark the chapter inactive or archived in Postgres
- hide or move created channels under an archived or failed-provisioning
  category
- disable panels
- preserve created roles/channels for audit unless the user explicitly
  approves destructive cleanup

If a provisioning run fails halfway through, resumable repair is the
default path. Destructive cleanup should be a separate, explicit,
approved operation.

## 14. Anti-scope (explicitly out of v1)

- Moderation tooling: there are no active moderators and no research
  evidence that a full mod-case system is the pain today.
- `moderator` ticket type: deferred because the `Moderator` role is
  currently empty, so plumbing a dedicated route now would be a half-
  solution. Add it later with a normal additive enum migration when real
  handlers exist.
- `chapter_incident` ticket type: deferred because no live chapter
  incident-handler surface exists yet, so building that route now would
  be plumbing for empty roles. Add it later with a normal additive enum
  migration when officers actually need a separate incident queue.
- Anonymous reporting: deeper trust and privacy surface than the current
  scope requires.
- Leveling / XP / engagement: AmariBot already handles the felt need.
- Calendar / events: Apollo and sesh are effectively unused; no active
  demand surfaced.
- Verification / CAPTCHA: Captcha.bot already solves this.
- Multi-server control plane: Humility only.
- Cross-server federation: same reason, plus large added complexity.
- Auto-moderation: out of scope for the current pain profile.
- Spam / raid defense: still handled by Captcha.bot and Discord
  AutoMod.
- Analytics dashboards: Postgres is the source of truth; a web dashboard
  is unnecessary for v1.
- DSR/GDPR self-service export tooling: manual DB export is sufficient
  at Humility’s current scale.
- Public web dashboard: no extra web surface in v1.
- Mobile-first custom client: Discord already is the client.
- Fully automated OCR self-training or fine-tuning: unnecessary before
  baseline accuracy is measured.
- Non-Humility generic bot packaging: this is a custom guild system, not
  a marketplace product.

## 15. Risks and mitigations

1. OCR accuracy risk. Mitigation: conservative acceptance thresholds,
   review-required state, gold-set measurement, and phase-2b fallback
   plus classical-plus-LLM cross-validation only if phase 2a needs it.
2. Player to Discord identity mapping risk. Mitigation: persistent
   `chapter_members`, auto-seeding from approved applications, explicit
   mapping commands, and unmatched-row review flows.
3. Supabase vendor dependency. Mitigation: plain Postgres schema,
   in-repo migrations, dump/restore portability, and no vendor-specific
   business logic.
4. Google Vision vendor dependency, plus Gemini if phase 2b is enabled.
   Mitigation: isolate those APIs to activity imports, persist raw
   inputs and outputs, and keep the classical OCR path as the primary
   baseline.
5. Role and category cap growth. Mitigation: preflight hard-limit
   checks, loud failure before mutation, and archived-chapter cleanup
   policy.
6. Permission drift over time. Mitigation: explicit channel-level
   overwrites on provision, periodic inspection, and no reliance on
   category sync for critical permissions.
7. Bounded-mutation bug while the bot has `Administrator`. Mitigation:
   one mutation wrapper, no implicit bulk helpers, and pre/post audit
   rows for every visible write.
8. Waitlist aging and UX friction. Mitigation: explicit waitlist state,
   queue filters, staff reminders for stale waitlisted applications, and
   audit history to prevent silent limbo.
9. Bot role hierarchy may block role management. Mitigation: preflight
   check that the bot’s highest role outranks Captcha.bot’s managed role
   and every managed chapter role; abort with a clear message if not.
10. Private-thread watcher semantics may be easy to get wrong.
    Mitigation: staging-guild tests for all thread membership paths and
    explicit watcher lists separate from claim-removal lists.

## 16. Open questions for hookpoint phase

- Which pieces of `daemon/claim.py` are worth keeping versus rewriting
  against the final watcher-aware claim model?
- Which parts of the pre-research config-loading shape can survive once
  forms are YAML-authored but DB-versioned?
- What is the best current `discord.py` support surface for modern modal
  components such as file upload, checkboxes, and radio-style choice?
- Does the current `server-manager` role position need to be raised
  before any role mutation can work?
- Which existing GUILD TEMPLATE channel names and overwrite patterns are
  worth preserving versus replacing with an explicit provisioning spec?
- Are there OSS examples worth borrowing for durable ticket transcript
  capture in private threads?
- What is the best implementation pattern for a lightweight in-process
  scheduler on Railway without introducing a second worker service?
- Are there Discord API constraints around thread membership,
  `MANAGE_THREADS`, and staff override behavior that require a narrower
  design than proposed here?

## 17. Cost model

Assumptions:

- one production Railway service plus one staging Railway service
- one production Supabase project and one staging project refreshed on
  demand
- ~900 screenshots/month
- Google Vision handles most imports
- Gemini is fallback-only, not primary

| Item | Assumption | Monthly cost |
| --- | --- | --- |
| Railway (production) | one small always-on service | `~$5-10` |
| Railway (staging) | one small service kept available for parity checks | `~$5` |
| Supabase (production) | Pro for live posture per D7 | `~$25` |
| Supabase (staging) | on-demand staging refresh workflow on free tier; accept auto-pause between test runs | `$0` |
| Google Cloud Vision | first 1,000 units free or near-free usage | `$0-2` |
| Gemini 3 Flash Preview fallback | fallback-only OCR escalation | `~$1` |
| Total, MVP with staging parity | prod Railway + staging Railway + prod Supabase Pro + OCR vendors | `~$36-43` |
| Total, higher-end live posture | same as above with modest Railway headroom | `~$41-48` |
