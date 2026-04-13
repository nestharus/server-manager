# Proposal 01: Humility Discord Daemon v1 Scope

## 1. Executive summary

Humility v1 should be a single always-on Discord daemon on Railway, backed by Supabase Postgres, with Supabase Storage for durable image evidence. Its scope is narrow: replace Gather, replace the broken ticket bot path, automate chapter creation, and remove the manual screenshot-to-spreadsheet activity workflow.

Discord remains the operator surface. `discord_cli.py` survives as a sibling inspection tool. The daemon owns live interactions, durable workflow state, transcript capture, OCR orchestration, and bounded Discord mutations. Postgres is the system of record; Discord messages and threads are operator projections over that record.

The sequence should follow the accepted Option C. Phase 0 delivers the daemon skeleton, schema, migrations, CI, logging, and `/daemon-ping`. Phase 1 delivers one working chapter application flow. Phase 2 adds screenshot OCR and flagging. Phase 3 adds the four ticket types. Phase 4 automates chapter provisioning. That order keeps the highest-risk visible-write surface last while reusing the same interaction, claim, and audit foundations.

The cost profile is modest. Railway and Supabase dominate spend. Google Vision primary OCR should stay near zero at MVP volume. Gemini fallback should also stay low because it only runs on ambiguous uploads. The complexity budget therefore belongs in correctness: auditability, reversible mutation patterns, transcript retention, schema versioning, and controlled OCR escalation.

## 2. High-level architecture

```text
                         Railway env vars / secrets
                                   |
                                   v
Discord Slash Commands / Buttons / Modals / Messages
                                   |
                                   v
                       +---------------------------+
                       | Humility daemon           |
                       | discord.py gateway client |
                       | interaction handlers      |
                       | OCR orchestrator          |
                       | mutation safety wrapper   |
                       | transcript/audit writers  |
                       +------------+--------------+
                                    |                \
                                    |                 \
                                    v                  v
                        Supabase Postgres          Supabase Storage
                        app + audit schemas        activity evidence
                                    |
                                    |
                        +-----------+-----------+
                        |                       |
                        v                       v
            Google Cloud Vision         Gemini 3 Flash Preview
         DOCUMENT_TEXT_DETECTION        fallback for low-confidence


discord_cli.py
  |  read-mostly Discord inspection
  |  DB reads, audits, diagnostics
  +--------------------------------------> Supabase Postgres / Discord API
```

The Discord gateway is the upstream event source. Slash commands, buttons, modal submits, thread events, and relevant messages arrive through one long-running `discord.py` process. That keeps interaction latency low and keeps transcript capture and claim updates in one place.

The daemon is the only live write service in v1. It owns workflow state machines, persistence, OCR routing, and visible Discord mutations. There is no separate API service because the accepted scope does not justify a second always-on surface yet.

Supabase Postgres is the source of truth. Applications, tickets, OCR uploads, activity rows, flags, provisioning runs, and audit events land there as durable records. Supabase Storage holds screenshot evidence because Discord attachment URLs are not the forever-retention path.

Google Cloud Vision is the primary OCR engine. Gemini 3 Flash Preview is the fallback only for ambiguous uploads. `discord_cli.py` remains a separate, read-mostly inspection tool for audits, diagnostics, and state comparison.

## 3. Data model

The schema should live in Postgres under `app` and `audit` schemas. `audit.audit_events` is append-only. All user-visible records use soft-delete or archival timestamps instead of hard delete.

```sql
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE app.application_status AS ENUM (
    'draft',
    'submitted',
    'claimed',
    'interview',
    'waitlist',
    'approved',
    'denied',
    'withdrawn',
    'promoted'
);

CREATE TYPE app.ticket_type AS ENUM (
    'server_support',
    'moderator',
    'chapter_support',
    'chapter_incident'
);

CREATE TYPE app.ticket_status AS ENUM (
    'open',
    'claimed',
    'closed',
    'promoted'
);

CREATE TYPE app.provisioning_status AS ENUM (
    'planned',
    'running',
    'completed',
    'failed',
    'rolled_back'
);

CREATE TYPE app.provisioning_step_status AS ENUM (
    'planned',
    'running',
    'completed',
    'failed',
    'rolled_back',
    'skipped'
);

CREATE TYPE app.activity_upload_status AS ENUM (
    'received',
    'parsed',
    'flagged_for_review',
    'corrected',
    'failed'
);

CREATE TYPE app.activity_row_status AS ENUM (
    'accepted',
    'corrected',
    'unmatched',
    'rejected'
);

CREATE TYPE app.flag_status AS ENUM (
    'open',
    'acknowledged',
    'resolved',
    'dismissed'
);

CREATE TYPE audit.audit_event_status AS ENUM (
    'planned',
    'succeeded',
    'failed',
    'rolled_back'
);

CREATE TABLE app.discord_users (
    discord_user_id BIGINT PRIMARY KEY,
    username TEXT,
    global_name TEXT,
    display_name_snapshot TEXT,
    is_bot BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_guild_at TIMESTAMPTZ
);

CREATE TABLE app.discord_roles (
    discord_role_id BIGINT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    role_name_snapshot TEXT NOT NULL,
    position_snapshot INTEGER,
    managed BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ
);

CREATE TABLE app.discord_channels (
    discord_channel_id BIGINT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_type TEXT NOT NULL,
    channel_name_snapshot TEXT NOT NULL,
    parent_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    archived_at TIMESTAMPTZ
);

CREATE TABLE app.chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guild_id BIGINT NOT NULL,
    slug TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    display_name TEXT NOT NULL,
    game_name TEXT NOT NULL,
    category_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    officer_lobby_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    created_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    archive_reason TEXT
);

CREATE TABLE app.chapter_roles (
    chapter_id UUID PRIMARY KEY REFERENCES app.chapters(id),
    chapter_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    public_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    applicant_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    member_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    officer_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    guild_war_role_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE app.chapter_channels (
    chapter_id UUID PRIMARY KEY REFERENCES app.chapters(id),
    applications_queue_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    chapter_support_queue_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    chapter_incident_queue_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    officer_lobby_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE TABLE app.chapter_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    in_game_name TEXT NOT NULL,
    normalized_in_game_name TEXT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at TIMESTAMPTZ,
    left_reason TEXT,
    created_from_application_id UUID,
    UNIQUE (chapter_id, discord_user_id, joined_at)
);

CREATE UNIQUE INDEX chapter_members_active_user_idx
    ON app.chapter_members (chapter_id, discord_user_id)
    WHERE left_at IS NULL;

CREATE UNIQUE INDEX chapter_members_active_ign_idx
    ON app.chapter_members (chapter_id, normalized_in_game_name)
    WHERE left_at IS NULL;

CREATE TABLE app.application_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    current_version_id UUID,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,
    UNIQUE (chapter_id, archived_at)
);

CREATE TABLE app.application_form_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_form_id UUID NOT NULL REFERENCES app.application_forms(id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    schema_json JSONB NOT NULL,
    component_plan_json JSONB NOT NULL,
    created_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (application_form_id, version_number)
);

ALTER TABLE app.application_forms
    ADD CONSTRAINT application_forms_current_version_fk
    FOREIGN KEY (current_version_id) REFERENCES app.application_form_versions(id);

CREATE TABLE app.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    application_form_version_id UUID NOT NULL REFERENCES app.application_form_versions(id),
    applicant_discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    current_status app.application_status NOT NULL,
    answers_json JSONB NOT NULL,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    claimed_at TIMESTAMPTZ,
    claimed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    review_queue_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    review_message_discord_id BIGINT,
    review_thread_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    interview_requested_at TIMESTAMPTZ,
    waitlisted_at TIMESTAMPTZ,
    waitlist_reason TEXT,
    decided_at TIMESTAMPTZ,
    decided_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    decision_reason TEXT,
    blacklist_on_deny BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ
);

CREATE INDEX applications_active_by_chapter_idx
    ON app.applications (chapter_id, current_status, opened_at DESC)
    WHERE archived_at IS NULL;

CREATE UNIQUE INDEX applications_active_per_user_idx
    ON app.applications (chapter_id, applicant_discord_user_id)
    WHERE current_status IN ('draft', 'submitted', 'claimed', 'interview', 'waitlist');

CREATE TABLE app.application_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES app.applications(id),
    from_status app.application_status,
    to_status app.application_status NOT NULL,
    actor_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX application_status_history_lookup_idx
    ON app.application_status_history (application_id, created_at ASC);

CREATE TABLE app.application_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    reason TEXT NOT NULL,
    source_application_id UUID REFERENCES app.applications(id),
    added_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    removed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    UNIQUE (chapter_id, discord_user_id, removed_at)
);

CREATE UNIQUE INDEX application_blacklist_active_idx
    ON app.application_blacklist (chapter_id, discord_user_id)
    WHERE removed_at IS NULL;

CREATE TABLE app.tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_type app.ticket_type NOT NULL,
    chapter_id UUID REFERENCES app.chapters(id),
    requester_discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    handler_role_discord_id BIGINT NOT NULL REFERENCES app.discord_roles(discord_role_id),
    current_status app.ticket_status NOT NULL,
    subject TEXT,
    opening_message_json JSONB NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    claimed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    queue_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    queue_message_discord_id BIGINT,
    thread_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    requester_left_server_at TIMESTAMPTZ,
    promoted_to_application_id UUID REFERENCES app.applications(id),
    closed_at TIMESTAMPTZ,
    closed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    close_reason TEXT,
    archived_at TIMESTAMPTZ
);

CREATE INDEX tickets_active_lookup_idx
    ON app.tickets (ticket_type, current_status, opened_at DESC)
    WHERE archived_at IS NULL;

CREATE TABLE app.ticket_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES app.tickets(id),
    discord_message_id BIGINT NOT NULL UNIQUE,
    thread_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    author_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    content_markdown TEXT,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    embeds_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    raw_event_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX ticket_messages_ticket_lookup_idx
    ON app.ticket_messages (ticket_id, created_at ASC);

CREATE TABLE app.activity_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    rule_name TEXT NOT NULL,
    metric_name TEXT NOT NULL DEFAULT 'points',
    comparison_operator TEXT NOT NULL CHECK (comparison_operator IN ('lt', 'lte', 'gt', 'gte')),
    threshold_value INTEGER NOT NULL CHECK (threshold_value >= 0),
    window_days INTEGER NOT NULL CHECK (window_days > 0),
    breach_count_required INTEGER NOT NULL CHECK (breach_count_required > 0),
    evaluation_mode TEXT NOT NULL CHECK (evaluation_mode IN ('consecutive', 'rolling_count')),
    review_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX activity_rules_active_idx
    ON app.activity_rules (chapter_id)
    WHERE archived_at IS NULL AND is_active = TRUE;

CREATE TABLE app.activity_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    uploaded_by_discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    source_discord_channel_id BIGINT NOT NULL REFERENCES app.discord_channels(discord_channel_id),
    source_discord_message_id BIGINT,
    discord_attachment_id BIGINT,
    captured_for_date DATE NOT NULL,
    storage_bucket TEXT NOT NULL,
    storage_object_path TEXT NOT NULL,
    sha256_hex TEXT NOT NULL,
    primary_ocr_provider TEXT NOT NULL DEFAULT 'google_vision_document_text_detection',
    fallback_ocr_provider TEXT NOT NULL DEFAULT 'gemini_3_flash_preview',
    current_status app.activity_upload_status NOT NULL,
    primary_ocr_payload_json JSONB,
    fallback_ocr_payload_json JSONB,
    processing_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    archived_at TIMESTAMPTZ,
    UNIQUE (storage_bucket, storage_object_path)
);

CREATE INDEX activity_uploads_chapter_date_idx
    ON app.activity_uploads (chapter_id, captured_for_date DESC);

CREATE TABLE app.activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_upload_id UUID NOT NULL REFERENCES app.activity_uploads(id),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    chapter_member_id UUID REFERENCES app.chapter_members(id),
    activity_date DATE NOT NULL,
    source_row_index INTEGER NOT NULL CHECK (source_row_index >= 0),
    player_name_raw TEXT NOT NULL,
    player_name_normalized TEXT NOT NULL,
    parsed_points INTEGER NOT NULL CHECK (parsed_points >= 0),
    parser_source TEXT NOT NULL CHECK (parser_source IN ('google_vision', 'gemini_fallback', 'manual')),
    row_confidence NUMERIC(5,4) NOT NULL CHECK (row_confidence >= 0 AND row_confidence <= 1),
    quoted_source_text TEXT NOT NULL,
    row_status app.activity_row_status NOT NULL,
    correction_note TEXT,
    corrected_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    corrected_at TIMESTAMPTZ,
    superseded_at TIMESTAMPTZ
);

CREATE INDEX activity_log_upload_idx
    ON app.activity_log (activity_upload_id, source_row_index ASC);

CREATE UNIQUE INDEX activity_log_current_member_day_idx
    ON app.activity_log (chapter_id, chapter_member_id, activity_date)
    WHERE chapter_member_id IS NOT NULL AND superseded_at IS NULL;

CREATE TABLE app.activity_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES app.chapters(id),
    chapter_member_id UUID NOT NULL REFERENCES app.chapter_members(id),
    activity_rule_id UUID NOT NULL REFERENCES app.activity_rules(id),
    latest_activity_log_id UUID REFERENCES app.activity_log(id),
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    breach_days INTEGER NOT NULL CHECK (breach_days >= 0),
    current_status app.flag_status NOT NULL DEFAULT 'open',
    summary TEXT NOT NULL,
    review_message_discord_id BIGINT,
    review_thread_discord_channel_id BIGINT REFERENCES app.discord_channels(discord_channel_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    resolution_note TEXT,
    archived_at TIMESTAMPTZ
);

CREATE INDEX activity_flags_open_idx
    ON app.activity_flags (chapter_id, current_status, created_at DESC)
    WHERE archived_at IS NULL;

CREATE TABLE app.provisioning_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by_discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
    confirmed_by_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    chapter_id UUID REFERENCES app.chapters(id),
    spec_json JSONB NOT NULL,
    dry_run_report_json JSONB NOT NULL,
    current_status app.provisioning_status NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    rollback_of_run_id UUID REFERENCES app.provisioning_runs(id),
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app.provisioning_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provisioning_run_id UUID NOT NULL REFERENCES app.provisioning_runs(id),
    step_order INTEGER NOT NULL CHECK (step_order > 0),
    step_key TEXT NOT NULL,
    current_status app.provisioning_step_status NOT NULL,
    discord_resource_kind TEXT,
    discord_resource_id BIGINT,
    db_table_name TEXT,
    db_row_primary_key TEXT,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (provisioning_run_id, step_order),
    UNIQUE (provisioning_run_id, step_key)
);

CREATE TABLE audit.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_name TEXT NOT NULL,
    operation_id UUID,
    actor_discord_user_id BIGINT REFERENCES app.discord_users(discord_user_id),
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('user', 'system')),
    target_kind TEXT NOT NULL,
    target_discord_id BIGINT,
    target_table_name TEXT,
    target_primary_key TEXT,
    event_status audit.audit_event_status NOT NULL,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    before_json JSONB,
    after_json JSONB,
    error_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX audit_events_lookup_idx
    ON audit.audit_events (operation_name, created_at DESC);
```

Table notes and nullability:

- `app.discord_users`: durable user identity snapshot. Nullable profile fields cover backfill or departed users. Soft-delete equivalent: `left_guild_at`.
- `app.discord_roles`: local mirror of Discord role IDs so chapter bindings can use foreign keys. Nullable `position_snapshot` covers partial backfills. Soft-delete column: `archived_at`.
- `app.discord_channels`: same pattern for channels and threads. Nullable `parent_discord_channel_id` covers top-level categories. Soft-delete column: `archived_at`.
- `app.chapters`: canonical chapter row. Nullable `officer_lobby_discord_channel_id` and `created_by_discord_user_id` cover imported or pre-provisioning records. Soft-delete column: `archived_at`.
- `app.chapter_roles`: one row per chapter mapping the six chapter role IDs. Nullable nothing except `archived_at`; the row is incomplete if any role ID is missing. Soft-delete column: `archived_at`.
- `app.chapter_channels`: one row per active chapter mapping the required queue and officer channels. Nullable nothing except `archived_at`; v1 treats these channels as mandatory. Soft-delete column: `archived_at`.
- `app.chapter_members`: roster plus in-game identity binding. Nullable `left_at`, `left_reason`, and `created_from_application_id` because active members have not left and some members will predate the daemon. Soft-delete equivalent: `left_at`.
- `app.application_forms`: stable per-chapter form identity. Nullable `current_version_id` only during initial draft creation. Soft-delete column: `archived_at`.
- `app.application_form_versions`: immutable version snapshots. Nullable `created_by_discord_user_id` for imports from repo YAML or migration scripts.
- `app.applications`: durable submission record and current state. Claim, review-thread, waitlist, and decision fields are nullable until the workflow reaches those states. Soft-delete column: `archived_at`.
- `app.application_status_history`: append-only transition log. Nullable `from_status` covers the initial insert; nullable actor covers system transitions.
- `app.application_blacklist`: per-chapter blacklist. Nullable `source_application_id` covers manual policy additions; removal fields stay null until removal. Soft-delete equivalent: `removed_at`.
- `app.tickets`: canonical ticket case record. Nullable `chapter_id` covers global ticket types; claim, thread, and close fields stay null until used. Soft-delete column: `archived_at`.
- `app.ticket_messages`: transcript store. Nullable `author_discord_user_id` because deleted users or webhooks may lack a durable user row. Nullable `content_markdown`, `edited_at`, and `deleted_at` because attachment-only messages exist and not every message is edited or deleted.
- `app.activity_rules`: compact rule grammar stored as rows, not free-form scripts. Soft-delete column: `archived_at`.
- `app.activity_uploads`: one screenshot ingestion record. Discord source IDs are nullable for future backfills; OCR payloads are nullable until processing completes. Soft-delete column: `archived_at`.
- `app.activity_log`: one parsed row from one upload. Nullable `chapter_member_id` covers unmatched names; correction fields stay null until a human edits the row. Soft-delete equivalent: `superseded_at`.
- `app.activity_flags`: derived rule breach records. Review refs and resolution fields are nullable until the flag is posted and resolved. Soft-delete column: `archived_at`.
- `app.provisioning_runs`: saga header for chapter creation and archival. Nullable `confirmed_by_discord_user_id`, `chapter_id`, `started_at`, `completed_at`, `rollback_of_run_id`, and `failure_reason` because not every planned run is confirmed or completed.
- `app.provisioning_steps`: step ledger for resume and rollback. Most resource reference columns are nullable because some steps only validate or write DB state.
- `audit.audit_events`: immutable audit trail for every bounded mutation. Nullable target IDs and snapshots because some events are planning or failure records before the target exists.

## 4. Applications subsystem

Application forms should be DB-stored, not YAML-backed in production. YAML remains useful as an import format, but it is the wrong system of record for a Railway-hosted workflow that needs versioning, auditability, and live chapter provisioning. Each chapter’s active form lives in `application_forms` + immutable `application_form_versions`. A form edit creates a new version row; it never rewrites history.

The user surface is `/apply chapter:<chapter>`, with autocomplete limited to active, non-archived chapters. The slash command performs three checks before opening the first interaction: the chapter exists and is active, the applicant is not blacklisted for that chapter, and the applicant has no active application in `draft`, `submitted`, `claimed`, `interview`, or `waitlist`. The blacklist is checked again on final submit to close the race where staff blacklists the user while they are midway through the form.

Rendering uses Discord’s current modal capabilities, not the older text-only assumption. The form planner should support string input, numeric input, single-select, multi-select, radio, checkbox, and file upload components. The planner turns one form version into one or more interaction pages constrained by Discord component limits. If a form fits inside one modal, it stays one modal. If it exceeds modal limits, the daemon opens a sequenced interaction session: modal page 1, then component follow-up or modal page 2 from the next interaction. The important design rule is that the form model is logical and stable; the component plan is a derived rendering artifact stored alongside the version. That lets the form change while keeping the historical render plan for old submissions.

On `/apply`, the daemon creates an `applications` row in `draft` with the target `application_form_version_id`, applicant ID, and empty answers. Each completed interaction page updates `answers_json`. Final submit transitions `draft -> submitted`, stamps `submitted_at`, and writes the immutable answer snapshot. This preserves abandoned starts, allows resume logic later without redesigning the schema, and gives staff a truthful audit trail about whether a user ever opened the form.

Once submitted, the daemon posts a review embed in the chapter’s applications queue channel and creates a private review thread in the same parent channel. The thread is created as a private thread, not a message-attached public thread. The queue message contains the chapter, applicant, submission time, current state, a compact answer summary, and buttons: `Claim`, `Interview`, `Waitlist`, `Approve`, `Deny`. The embed also includes a link or mention to the private thread. The thread is seeded with the applicant, all chapter officers for that chapter, the bot itself, and any preserved central override members configured by policy. Because claim-based visibility only works if ordinary reviewers do not have `MANAGE_THREADS`, the channel permission model must avoid handing `MANAGE_THREADS` to every handler role.

State machine:

- `draft -> submitted`
- `submitted -> claimed`
- `submitted -> interview`
- `submitted -> waitlist`
- `submitted -> approved`
- `submitted -> denied`
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
- any active state -> `withdrawn` only by applicant or staff

The distinction between `interview` and `waitlist` must be operational, not cosmetic. `interview` means an officer is actively working the case and expects a follow-up conversation or extra evidence; the claimer remains the active owner. `waitlist` means the application is paused for capacity, timing, or chapter demand reasons; the application is not approved and is not currently “in interview.” When an application moves to `waitlist`, the daemon should re-expand thread membership from the claimer-only set back to chapter officers so another officer can later pick it up without staff-side manual repair.

`Claim` uses the shared claim-visibility helper. On success, the application transitions to `claimed`, stores `claimed_by_discord_user_id`, and narrows the review thread to the applicant, the claimer, the bot, and any explicitly preserved override users. `Interview` transitions the record without changing the answer snapshot and posts the follow-up request in-thread.

`Approve` must be a bounded mutation sequence, not raw Discord calls scattered through the handler. The daemon adds the chapter’s `member_role_id` and base `chapter_role_id`, removes the chapter `applicant_role_id`, inserts or updates the `chapter_members` row using the submitted in-game name, records the status transition, DMs the applicant with the outcome, posts a terminal embed in the thread, and archives the thread. The daemon should not auto-assign `guild_war_role_id`; that remains chapter-policy specific and manual unless a later requirement justifies it.

`Deny` opens a short staff modal requiring a reason and allowing a `Blacklist this applicant for this chapter` checkbox. The reason is stored in both `applications.decision_reason` and `application_status_history.note`. If the checkbox is selected, the daemon inserts an `application_blacklist` row tied back to the application. The daemon DMs the applicant with the reason, marks the application denied, posts the denial in-thread, and archives the thread.

Retention is full. Nothing is hard-deleted. Old applications remain queryable forever. “Deleting” a queue message or archiving a thread is a Discord UX action, not data deletion. The DB record, status history, answer snapshot, and denial or waitlist notes remain intact.

Form schema evolution is handled by immutable version snapshots. If Dark Nemesis changes a timezone question from select to radio next month, the new version becomes active for new applicants only. Old submissions still render exactly as answered because the old `schema_json` and `component_plan_json` stay attached to the submission’s `application_form_version_id`.

## 5. Tickets subsystem

Tickets and applications should share the same queue-thread-claim foundation, but they should remain separate state machines and tables because their routing, transcript needs, and terminal actions differ.

The four ticket types are:

- `server_support`: global support requests routed to `Staff`.
- `moderator`: reports and moderator-facing cases routed to `Moderator`; `Trial Mod` gets read-only visibility at the queue parent but cannot speak in threads.
- `chapter_support`: chapter-level support routed to the selected chapter’s officer role.
- `chapter_incident`: chapter-level incident or conflict cases routed to the selected chapter’s officer role, with the stronger expectation that central staff may later inspect via override.

The primary open surface should be one slash command plus persistent panels. `/ticket open type:<type> chapter?:<chapter> subject:<text> description:<text>` is the universal fallback. Persistent panels should live in the existing global `#support` surface for `server_support` and `moderator`, and in each chapter’s member-facing channel for `chapter_support` and `chapter_incident`. Buttons reduce friction for ordinary members. Slash commands remain necessary for accessibility, autocomplete, and operator backfill.

Ticket creation writes the `tickets` row first, posts a queue embed second, and creates the private thread third. For `moderator` tickets, the parent queue channel permissions must distinguish `SEND_MESSAGES_IN_THREADS` from `SEND_MESSAGES`; `Trial Mod` gets read visibility while denied thread posting.

Claim mechanics are shared with applications. The common helper receives the thread, requester, claimer, and a preserved-user set, then mutates explicit private-thread membership. It must not assume that role-based visibility alone is enough, because the goal is to narrow the case after claim.

Transcript persistence should use a hybrid approach. The daemon listens to gateway message-create, message-update, and message-delete events for any thread channel linked to an open ticket and writes those into `ticket_messages` in near real time. On close, the daemon runs a reconciliation pass over the full thread history to backfill missed events and confirm the transcript is complete before final archive. Gateway events give freshness; close-time reconciliation gives durability if the process restarts.

Close flow: the closer clicks `Close`, supplies a reason, the daemon persists the close record, posts a terminal summary, reconciles transcript history, marks the ticket `closed`, and archives the thread. The queue message is edited to reflect closure. Tickets are never hard-deleted. The transcript remains in `ticket_messages` even if the thread eventually auto-archives or is manually removed later.

If the requester leaves the server mid-ticket, the ticket remains valid. The daemon marks `requester_left_server_at`, updates the queue embed, and stops assuming the user can be re-added to the private thread. Staff can continue discussing and close the case. Any final DM attempt is best-effort and logged. A user leaving the guild is not a reason to lose the ticket record.

Ticket-to-application promotion should exist, but as a controlled handoff rather than magical conversion. A staffer can click `Promote to Application`, choose the target chapter, and the daemon creates a linked `applications` record prefilled with the ticket’s description plus any structured fields that can be safely mapped. The requester then receives a button or slash-command shortcut to finish the real chapter application form. The original ticket transitions to `promoted`, links to the new application, and closes. This preserves the conversation and prevents staff from manually copying context around.

## 6. Activity tracking subsystem

The input surface should be an officer-only slash command, not DM, and not “post images anywhere and hope the bot sees them.” The core command should be `/activity upload chapter:<chapter> date:<YYYY-MM-DD> image:<attachment>`. It should only be executable by chapter officers for that chapter, `Staff`, or `Administrator`. The command can be run from the chapter officer lobby or a global staff ops channel; the channel context is recorded, but the chapter argument is explicit so the upload is never inferred from channel name alone.

Roster binding is ongoing, not one-time. `chapter_members` is initially seeded from approved applications, but officers need explicit maintenance commands for roster corrections and late links: `/chapter roster link`, `/chapter roster rename`, `/chapter roster remove`, and `/chapter roster import` from a simple CSV attachment if needed. Activity tracking depends on a maintained `(chapter, in_game_name, discord_user_id)` mapping. The daemon should therefore treat roster quality as a first-class operational concern, not as an afterthought behind OCR.

OCR pipeline:

1. Receive the image through the slash command. Immediately copy the attachment into Supabase Storage, hash it, create the `activity_uploads` row in `received`, and acknowledge the interaction.
2. Run optional preprocessing. V1 should support chapter-configurable crop rectangles, grayscale normalization, contrast boost, 2x upscale for small text, and light deskew if the detected angle is materially off-axis. Preprocessing stays conservative; it should never overwrite the stored original.
3. Call Google Cloud Vision `DOCUMENT_TEXT_DETECTION` on the preprocessed image.
4. Parse rows using geometric grouping, not line breaks alone. The parser should cluster words by y-axis overlap into row bands, sort tokens in each row by x-position, treat the rightmost numeric cluster as the score column, and treat the remaining visible text to the left as the player name. Header rows and obviously non-row UI chrome are filtered by regexes and minimum numeric confidence.
5. Compute row confidence. Each row gets a score derived from OCR token confidences, whether exactly one numeric score was found, whether the parsed name matches a current roster entry exactly or fuzzily, and whether the row shape matches the chapter’s expected table pattern.
6. Decide among three outcomes per upload: accept directly, flag for officer review, or escalate to Gemini. Direct accept only happens when the parser finds a coherent row set and the rows meet confidence and validation thresholds. Flag-for-review is used when the rows are usable but imperfect, for example unknown names or low-confidence digits. Gemini escalation is used when the classical result is too weak to trust without a second extraction path.
7. Gemini 3 Flash Preview fallback receives the original image plus the classical OCR text blocks and a strict JSON schema. The prompt requires an array of rows with `player_name`, `score`, `quoted_source_text`, `row_index_guess`, and `confidence_reason`. The model is instructed to quote only visible text and to omit rows it cannot justify.
8. Hallucination controls are mandatory. The daemon rejects fallback output when quoted text cannot be found in either the image-derived OCR text or the model’s own span references, when row count differs too far from the classical parse without explanation, or when the score format violates chapter expectations. The daemon should also compare Gemini rows back against roster candidates and run a second-pass validation that no accepted score row lacks an auditable text basis.
9. Persist final rows into `activity_log`, link matched rows to `chapter_members`, leave unmatched rows with `chapter_member_id NULL`, update `activity_uploads.current_status`, and then evaluate active `activity_rules` for the affected chapter and date window.

The rule language should be row-backed in the database, not YAML and not a free-form DSL. V1 only needs a compact grammar expressed by columns: metric, operator, threshold, window length, and required breach count. “Flag anyone under 50 points for 3 consecutive days” becomes `metric_name='points'`, `comparison_operator='lt'`, `threshold_value=50`, `window_days=3`, `breach_count_required=3`, `evaluation_mode='consecutive'`.

Flag output should post to the chapter’s officer lobby or designated activity review channel stored on the rule. DM is the wrong primary surface because activity management is a chapter workflow, not a private one-person workflow. The bot posts one summary embed per upload or per rule evaluation batch, then opens or links a review thread when manual correction is needed.

Mis-scanned rows must be correctable from Discord. V1 should support row-level correction buttons on the review message: `Link Member`, `Edit Score`, `Add Missing Row`, `Reject Row`, and `Confirm Upload`. Each button opens a focused modal for one correction. Corrections create new `activity_log` versions by superseding the prior row; they do not overwrite history.

If a screenshot contains a new player before the roster is updated, the row is stored as `unmatched`, displayed in the review UI, and can be linked to a Discord user later. The upload is still retained. Unknown names are a review problem, not a discard condition.

Historical backfill is allowed. Officers can upload an image with an explicit past `date:` value, and the daemon processes it normally. If a current row already exists for that member and day, the new corrected value supersedes the prior active row rather than deleting it. That supports backfill and correction without violating full-retention requirements.

## 7. Chapter provisioning subsystem

Chapter creation should start from an admin-only slash command, not from the CLI. Provisioning is a visible-write workflow that benefits from inline preview, confirmation, progress updates, and audit linkage inside Discord where the operator already is. The CLI can still help generate or validate a chapter spec locally, but it should not be the primary mutation trigger.

The entrypoint should be `/chapters create spec:<attachment>`. The attachment is a YAML or JSON spec containing chapter name, slug, game, initial officers, form questions, activity rules, and any non-default channel options. This keeps the trigger to one command while still allowing structured nested input. The daemon validates the spec, runs a dry-run capacity check, writes `provisioning_runs.current_status='planned'`, posts a preview back to the requester, and only starts the visible writes after an explicit `Confirm` button press by an authorized admin.

The create saga runs these steps in order, each with a `provisioning_steps` row and paired audit events:

1. Create the six chapter-specific roles cloned from templates and renamed with the chapter prefix.
2. Create the chapter category with base overwrites.
3. Create the chapter channels from the template plus the extra queue channels required for v1.
4. Apply channel-level overwrites explicitly to every created channel. The design should not rely on category inheritance alone because that is exactly the kind of permission drift trap the research identified.
5. Write the `chapters`, `chapter_roles`, and `chapter_channels` rows to Postgres.
6. Insert the application form and first immutable form version.
7. Insert the initial activity rules.
8. Post the application panel in the chapter applications channel and pin it.

This is not transactional in the database sense because Discord mutations are external side effects. The right model is a saga with resume and rollback support. Each step records created Discord IDs and DB IDs. If step 6 fails after channels already exist, the run lands in `failed`, the progress message tells the operator exactly which step failed, and the operator can choose `Resume` or `Rollback`.

Resume is the primary recovery path. The daemon should first attempt to reuse already-created resources recorded in completed provisioning steps. It should only create a missing role or channel when the recorded step is absent or explicitly failed before resource creation.

Rollback is explicit and reverse-ordered. The daemon should remove the application panel, archive or delete newly created empty channels, delete newly created roles if no members have been assigned, and mark any DB rows archived. If the provisioning run reached a point where humans may already have interacted with the created channels, rollback should prefer archival and disablement over destructive deletion. The guiding rule is to avoid silently destroying human-created residue.

Chapter archival uses the same saga framework. It marks the chapter archived in Postgres, disables new applications and tickets for that chapter, archives queues and category channels, records the archive reason, and leaves historical application, ticket, roster, and activity data intact forever.

Role and category caps must be checked before confirmation. The dry run should compute `current + projected` counts against Discord’s hard caps and also enforce internal guardrails. A sensible v1 rule is to fail chapter creation when the resulting server would exceed 240 roles or 45 categories, leaving headroom for emergencies and future system roles rather than aiming for the literal maximums.

Provisioning UX should be explicit. The requester sees an ephemeral validation summary immediately, then a progress message showing step-by-step completion with links to created resources as they become available. The final summary includes the created role IDs, channel IDs, and any warnings such as role-headroom percentage.

## 8. Shared infrastructure

The claim-visibility helper should be a shared service used by both applications and tickets. Its interface should accept the thread ID, requester user ID, optional claimer user ID, the set of preclaim handler user IDs, and the set of preserved override user IDs, and return the before/after membership snapshot plus unresolved members. The helper owns thread membership reconciliation only. It does not own state-machine transitions.

Every visible Discord mutation should go through a mutation safety wrapper. The wrapper records a `planned` audit event before the mutation, executes exactly one bounded Discord API operation, captures the resulting snapshot or error, and records a `succeeded`, `failed`, or `rolled_back` event after the operation.

Bounded mutation patterns are non-negotiable because the bot will operate with high privilege. Helpers must target one concrete object and one concrete intended change. Example: `add_role(member_id, role_id)` is acceptable; `sync_roles_for_all_members(chapter_id)` is not a v1 helper. `set_channel_overwrite(channel_id, target_role_id, overwrite_payload)` is acceptable; “clone all overwrites from category to every channel in the server” is not. The code should make bulk operations impossible by default and require explicitly enumerated targets even inside provisioning runs.

Background jobs should use Railway Cron for scheduled work rather than an in-process scheduler. The live daemon remains one process. Scheduled evaluation tasks such as daily waitlist reminders, transcript reconciliation sweeps, and periodic activity-flag recomputation should run as one-shot management commands in ephemeral Railway cron containers against the same repo and database. That avoids leader-election problems and missed schedules during daemon reconnects.

## 9. Deployment

Dockerfile sketch: `python:3.12-slim` base, minimal system image packages for preprocessing, pinned Python dependencies, source plus migrations copied in, Alembic run in a release step, entrypoint `python -m daemon`.

Railway service configuration:

- One always-on web-less worker service for the daemon.
- Start command: `python -m daemon`.
- Release command: `alembic upgrade head`.
- Region: same region family as Supabase to minimize DB latency.
- Health check: expose a tiny in-process HTTP `/healthz` endpoint from the daemon that reports last gateway heartbeat, DB connectivity, and whether the bot is in a reconnect loop. This stays inside the same process; it does not justify a separate API service.

Supabase project layout:

- One production project and one staging project.
- Schemas: `app` for operational tables, `audit` for append-only audit history.
- Storage buckets: `activity-evidence` for screenshots; optional future buckets for ticket or application attachments if those become required.
- Row-level security: disabled on `app` and `audit` tables in v1 because only the trusted daemon service role uses them. If a future web app is added, expose read models or views with RLS then instead of retrofitting policies under time pressure.

Secrets management:

- Railway stores `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`, `GOOGLE_CLOUD_VISION_KEY`, and `GEMINI_API_KEY`.
- The daemon reads secrets only from Railway environment variables in production.
- Local `.env` remains for development and the read-only CLI only.
- Supabase storage and DB access should use separate credentials if practical: least-privilege runtime DB user plus service-role-backed storage operations.

Migration tool: Alembic. The schema is relational, versioned, and expected to evolve under active development. Alembic is the least surprising migration tool in the Python/Postgres stack and fits the project’s expected future direction better than hand-written bootstrapping scripts.

Monorepo layout:

- `daemon/`: live Discord daemon package.
- `discord_cli.py`: sibling read-mostly inspection tool.
- `migrations/`: Alembic environment and SQL revisions.
- `forms/` and draft docs remain reference material only until hookpoint research decides what survives.
- `proposals/`, `research/`, `risk/`, and `docs/` remain planning artifacts.

## 10. Observability

Logs should be structured JSON to stdout so Railway captures them cleanly. Minimum fields: timestamp, severity, subsystem, guild ID, chapter ID when relevant, object IDs, OCR provider, audit operation name, and exception class.

Metrics should be exposed from the same lightweight health server as Prometheus-style counters and gauges. The important v1 metrics are:

- command invocations by command name and result
- active applications by state
- active tickets by type and state
- claim operations and failures
- OCR upload counts by outcome
- Google Vision latency and error rate
- Gemini escalation rate
- row confidence distribution
- unmatched roster row count
- mutation wrapper failures by operation type
- gateway reconnect count and current session age

Alerting should wake the owner for only the truly operational failures:

- daemon process down or stuck reconnecting
- Supabase DB connectivity lost for sustained duration
- migration failure on deploy
- Google Vision quota/auth failures causing all activity uploads to fail
- Gemini auth failure only if fallback is frequently needed
- audit wrapper failure rate above a threshold for role or channel mutations

The blast radius boundaries should be strict. Activity tracking failures must not take down applications or tickets. OCR work should run in a bounded async task queue with timeouts and exception isolation. A failed OCR upload becomes a failed upload record and an officer-visible error message. It does not crash the gateway client or block unrelated interactions.

## 11. Testing strategy

Unit tests should cover the places where correctness can be decided without Discord: application and ticket state transitions, claim-membership planning logic, form-version rendering plans, activity row parsing, OCR escalation thresholds, activity-rule evaluation, provisioning dry-run validation, and mutation-wrapper audit behavior.

Integration tests should sit above unit tests and below a real Discord server. Discord API calls should sit behind narrow service helpers so tests can run against fake guild/channel/thread objects and stubbed REST responses.

Staging should exist. The cleanest v1 choice is a separate staging Discord guild plus the staging Supabase project. A sandbox category inside the production Humility guild is not good enough for provisioning, permission, and role-cap tests because it cannot safely reproduce the real visible-write surface. The production guild is the wrong place to test role-cloning failures.

Manual first-deploy checklist:

- `/daemon-ping` responds.
- one chapter form opens and submits correctly.
- review embed and private thread are created.
- claim narrows thread membership correctly.
- approve adds the intended roles and removes applicant role.
- deny captures reason and optionally blacklists.
- ticket creation, claim, transcript capture, and close work for all four types.
- one activity upload succeeds on the classical path.
- one low-confidence upload escalates to Gemini and lands in review.
- one chapter provisioning dry run passes and one staging chapter create/rollback cycle completes.

OCR accuracy measurement needs a retained gold corpus. Before the subsystem is trusted, Humility should assemble a labeled screenshot set from its real games and scoreboards. The daemon then measures row precision, score accuracy, roster match rate, fallback rate, and human-correction rate. Ambiguous rows should be flagged, not guessed.

## 12. Sequencing plan (Option C)

### Phase 0: foundations

Definition of done: Railway deploys a single daemon service, Supabase schema exists, Alembic is wired, structured logging is live, `/daemon-ping` works in staging and production, and audit events can be written.

Demoable outcome: the owner can invoke `/daemon-ping`, inspect the live build version, and verify DB connectivity and health metrics.

Dependencies for next phase: stable Discord auth, stable DB connectivity, migrations, and the mutation wrapper skeleton.

### Phase 1: applications

Definition of done: one active chapter has a working form, `/apply` opens the form, submissions persist, review embed plus private thread are created, officers can claim/interview/waitlist/approve/deny, approval mutates roles and roster rows, denial can blacklist, and DMs are sent when possible.

Demoable outcome: a staging applicant completes the full flow from slash command to approval and role assignment.

Dependencies for next phase: claim helper, audit logging for role mutations, and stable thread handling.

### Phase 2: activity tracking

Definition of done: officers can upload screenshots, evidence is stored durably, Google Vision path works, Gemini fallback works, rows persist to `activity_log`, active rules compute flags, and officers can correct rows from Discord.

Demoable outcome: one real or staging screenshot produces accepted rows and a rule-based flag summary.

Dependencies for next phase: storage integration, async job isolation, roster bindings from applications, and stable officer-channel posting.

### Phase 3: tickets

Definition of done: all four ticket types can be opened, routed, claimed, transcripted, promoted where appropriate, and closed with full transcript retention.

Demoable outcome: a member opens each ticket type, staff claims it, messages appear in `ticket_messages`, and the ticket closes cleanly.

Dependencies for next phase: shared claim helper, queue/thread infrastructure, and close-time reconciliation logic.

### Phase 4: chapter provisioning automation

Definition of done: an admin can submit a chapter spec, receive a dry-run preview, confirm creation, watch progress, and end with a fully provisioned chapter including roles, channels, form, activity rules, and application panel. Resume and rollback paths both work in staging.

Demoable outcome: a new staging chapter appears end to end from one confirmed provisioning run, then archives cleanly.

Dependencies: everything earlier. Provisioning consumes the form engine, activity-rule model, mutation safety wrapper, and audit system. It should not land before those subsystems exist for real.

## 13. Rollback plan

Phase 0 rollback is redeploying the prior Railway image and, if needed, rolling back to the previous Alembic revision only when the newer schema is not yet in use. Because this is the foundation phase, DB rollback should be treated cautiously and only for clearly reversible migrations.

Phase 1 rollback is redeploying the previous daemon image and disabling the application slash command and panel if needed. Existing application data remains in Postgres. If a role-mutation bug appears, corrective role removals are executed through the same bounded mutation wrapper with audit events, not through ad hoc scripts.

Phase 2 rollback is disabling `/activity upload` and any review buttons while leaving all stored evidence and parsed rows intact. No data needs to be destroyed. If the OCR parser is wrong, corrected rows supersede prior rows and the subsystem can be paused without affecting applications or tickets.

Phase 3 rollback is disabling ticket panel buttons and slash commands, then leaving already-open tickets readable while staff closes or migrates them manually. Transcript capture data remains.

Phase 4 rollback is provisioning-run specific. If a create run fails, the operator either resumes or rolls back that exact run. Rollback walks `provisioning_steps` in reverse order, removes the application panel, archives or deletes empty created channels, removes unused created roles, archives any written chapter rows, and records `rolled_back` audit events. If humans have already begun using the created chapter, rollback archives rather than deletes.

## 14. Anti-scope (explicitly out of v1)

- Full moderation system. Research and decisions explicitly put moderation outside the first build; moderator tickets are in scope, but a full moderation bot is not.
- Web reviewer dashboards. Discord is the operator surface in v1; adding a web UI creates extra surface area before the core workflows are proven.
- Multi-guild tenancy. The daemon is for Humility guild `900000000000000001`, not a generic SaaS.
- Arbitrary OCR provider plug-in marketplace. The OCR boundary should be clean, but v1 only needs Google Vision primary and Gemini fallback.
- Automatic punishments or kicks from activity rules. v1 flags members for officer review; it does not auto-enforce.
- Cross-chapter transfer workflow. Officers can manually resolve transfers in v1; dedicated transfer flows can come later if they become a real pain point.
- Analytics dashboards beyond operational summaries. v1 needs durable records and inspections, not BI tooling.
- Public applicant portals or applicant self-service status pages. Discord DMs and thread outcomes are sufficient for v1.
- Spreadsheet sync. The goal is to replace the manual spreadsheet workflow, not keep two systems in parallel.

## 15. Risks and mitigations

- OCR accuracy risk. Mitigation: classical OCR primary, strict escalation thresholds, row-level confidence, gold-corpus evaluation, and manual correction UI before trusting ambiguous rows.
- Player-to-Discord identity mapping risk. Mitigation: make `chapter_members` and roster linking explicit, seed from approved applications, and treat unmatched rows as review-required rather than auto-linked guesses.
- Supabase vendor dependency. Mitigation: keep the schema in plain Postgres, use Alembic, avoid Supabase-only SQL tricks in core tables, and keep storage object references portable.
- Google Vision and Gemini vendor dependency. Mitigation: keep OCR orchestration behind one subsystem boundary, store raw OCR payloads, and make fallback invocation explicit so a different provider can replace it later if needed.
- Role and category cap growth. Mitigation: dry-run cap checks with internal guardrails below Discord hard limits, and use threads for cases instead of per-item channels.
- Permission drift over time. Mitigation: channel overwrites are applied explicitly by provisioning, audited, and later inspectable via `discord_cli.py`; do not rely on category inheritance staying correct forever.
- Bounded-mutation bug while the bot has Administrator. Mitigation: all visible writes go through one wrapper, helper interfaces only accept concrete targets, and no bulk mutation helper is exposed in v1.
- Waitlist aging and UX friction. Mitigation: separate `waitlist` from `interview`, log reasons, re-expand reviewer visibility on waitlist, and run scheduled reminders for long-waiting cases.
- Daemon restart or disconnect during transcript capture. Mitigation: gateway event writes plus close-time reconciliation, so missed live events can be backfilled.
- Requester leaves the server mid-ticket or application. Mitigation: treat Discord membership as mutable but keep durable user IDs and records; closure and audit do not depend on the user still being present.

## 16. Open questions for hookpoint phase

- Which pieces of the existing `daemon/` draft are worth preserving as implementation hookpoints, especially the current config loader, claim helper, and application review view?
- Does `discord.py 2.7.1` already expose enough stable helpers for the richer modal components this proposal assumes, especially file upload and radio/checkbox support?
- Are there OSS reference implementations for claim-based private-thread workflows that are operationally cleaner than the current draft helper?
- What is the exact existing meaning of the six chapter template roles in Humility’s live guild, especially the distinction between `Chapter`, `Chapter Public`, and `Chapter Member`?
- Should activity review posts live in each chapter officer lobby or in one global staff-ops review channel with chapter tagging?
- Is there any pre-research data worth importing from Gather or ticketsbot exports before v1 goes live?
- What is the right staging guild topology so provisioning, role hierarchy, and moderator-ticket permissions can be tested without production risk?
- Does the current `discord_cli.py` command structure already have natural seams for DB-backed inspection commands, or should a small shared read-model layer be introduced first?

## 17. Cost model

Assumptions:

- one always-on Railway worker
- one production Supabase project, one free staging project
- low MVP volume: roughly 150 to 600 activity screenshots per month
- Google Vision used on all uploads
- Gemini used only on a minority of ambiguous uploads

Estimated monthly cost:

- Railway: about `$5-10/month` for one small always-on service.
- Supabase: production should be budgeted as paid once the daemon becomes the operational system of record; assume about `$25/month` for prod, with staging on free. The absolute cheapest MVP could start on free, but that is not the recommendation once real retention and audit matter.
- Google Cloud Vision: effectively `$0/month` under the first 1,000 images, and still likely only `$0-2/month` at MVP volume.
- Gemini 3 Flash Preview fallback: about `$1/month` at MVP volume if fallback stays rare.

Recommended operating total: about `$31-38/month`.

Cheapest plausible early total if production remains on free tier briefly: about `$6-13/month`.

The cost model is therefore dominated by the hosting and database choices, not by OCR. That supports the proposal’s choice to optimize for operational correctness and retention rather than over-optimizing per-image spend.
