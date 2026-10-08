# Proposal 01: Humility Discord Daemon v1 Scope

## 1. Executive summary

Humility v1 should be a single always-on Discord daemon on Railway, backed by Supabase Postgres, with Supabase Storage for durable screenshot evidence. Its scope stays anchored to the four validated problem areas: applications, activity tracking, tickets, and chapter provisioning. The shape does not change: Discord remains the primary operator surface, `discord_cli.py` remains a sibling inspection tool, Postgres remains the system of record, and Discord messages and threads remain operator projections over durable records.

This revision trims implementation surface where the risk review showed overbuild. Applications remain the first fully realized workflow. Activity tracking is split into Phase 2a and Phase 2b so the OCR subsystem does not become one monolithic blocker. Tickets ship in v1 with `server_support` only. `chapter_support` and `chapter_incident` wait until real chapter infrastructure exists; `moderator` waits until the `Moderator` role is actually staffed. Ticket transcript capture is simplified to close-time full-history fetch in v1 rather than real-time gateway mirroring plus reconciliation.

Chapter provisioning also stays in scope, but the v1 shape is narrower than the original proposal. Humility currently has no live chapters, so the first chapter used for applications and activity tracking is a one-time manual bootstrap dependency created from the existing template structure before provisioning automation ships. Phase 4 then automates subsequent chapter creation with auditability, dry-run validation, explicit confirmation, and recorded created-resource IDs, but without a heavyweight resume/rollback engine that Humility's expected chapter volume does not justify.

The cost profile is still modest. Railway and Supabase dominate spend. Google Vision primary OCR should stay near zero at MVP volume, and Gemini fallback should remain low if escalation is reserved for ambiguous uploads. The complexity budget therefore belongs in correctness and operational safety: durable records, schema versioning, secret-scrubbed audit/logging, bounded Discord mutations, rate-limit-aware execution, and reversible operator actions where reversal is justified.

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
                       | audit / transcript writer |
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
         DOCUMENT_TEXT_DETECTION        fallback for ambiguous OCR


discord_cli.py
  |  read-mostly Discord inspection
  |  DB reads, audits, diagnostics
  +--------------------------------------> Supabase Postgres / Discord API
```

The Discord gateway is the upstream event source for live workflows. Slash commands, buttons, modal submits, thread events, and relevant member events arrive through one long-running `discord.py` process. That keeps interaction latency low and keeps review flows, claim transitions, and bounded Discord writes in one place.

The daemon is the only live write service in v1. It owns workflow state machines, persistence, OCR routing, transcript capture at ticket close, and visible Discord mutations. There is no second always-on API service in v1. If application input has to move to richer web forms because the required Discord components are not actually supported through the chosen library, that web surface is a narrow replacement for the application intake workflow; the operator workflow, review actions, and durable state remain centered on the daemon and the same Postgres records.

Supabase Postgres is the source of truth. Applications, tickets, OCR uploads, activity rows, flags, provisioning runs, and audit events land there as durable records. Supabase Storage holds screenshot evidence because Discord attachment URLs are not the forever-retention path.

Google Cloud Vision is the primary OCR engine. Gemini 3 Flash Preview is the fallback only for ambiguous uploads, and only after the Phase 2b confidence and validation path exists. `discord_cli.py` remains a separate, read-mostly inspection tool for audits, diagnostics, and state comparison.

## 3. Data model

The schema should live in Postgres under `app` and `audit` schemas. `audit.audit_events` is append-only by convention in v1 and stores logical mutation context, not raw transport payloads. All user-visible records use soft-delete or archival timestamps instead of hard delete. All database writes use parameterized queries; no user input is interpolated into SQL strings.

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
    'withdrawn'
);

CREATE TYPE app.ticket_type AS ENUM (
    'server_support'
);

CREATE TYPE app.ticket_status AS ENUM (
    'open',
    'claimed',
    'closed'
);

CREATE TYPE app.provisioning_status AS ENUM (
    'planned',
    'validated',
    'running',
    'completed',
    'failed',
    'cleaned_up'
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
    requester_discord_user_id BIGINT NOT NULL REFERENCES app.discord_users(discord_user_id),
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
    deleted_at TIMESTAMPTZ
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
    row_confidence NUMERIC(5,4) CHECK (row_confidence IS NULL OR (row_confidence >= 0 AND row_confidence <= 1)),
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
    validation_report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_resources_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    cleanup_report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_status app.provisioning_status NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cleaned_up_at TIMESTAMPTZ,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

- `app.discord_users`, `app.discord_roles`, and `app.discord_channels` are durable Discord identity mirrors. Soft-delete equivalents are `left_guild_at` or `archived_at`.
- `app.chapters`, `app.chapter_roles`, and `app.chapter_channels` define the current chapter graph. `chapter_channels` stores only the channels v1 actually depends on: the applications queue and officer lobby. Chapter-scoped ticket queues are deferred with the ticket types that need them.
- `app.application_forms` and `app.application_form_versions` keep form definitions in Postgres, not YAML. `schema_json` stores the logical form shape. `component_plan_json` stores the derived rendering plan for a specific version and remains document-shaped JSONB rather than a dumping ground for data with stable columns.
- `app.applications`, `app.application_status_history`, and `app.application_blacklist` keep the application workflow durable and queryable forever. `answers_json` and `attachments_json` are immutable submission snapshots tied to one form version.
- `app.tickets` and `app.ticket_messages` store only the `server_support` ticket workflow in v1. Transcript capture is a normalized message history fetched at close time rather than a raw gateway-event archive.
- `app.activity_rules`, `app.activity_uploads`, `app.activity_log`, and `app.activity_flags` separate known structure from document payloads. Rules stay column-backed; OCR provider payloads stay in JSONB because their structure is vendor-defined.
- `app.activity_log.row_confidence` is nullable so Phase 2a can persist basic extraction before Phase 2b calibration and fallback logic lands.
- `app.provisioning_runs` keeps the requested spec, dry-run validation report, created resource IDs, and any explicit cleanup report in one row. This preserves auditability without a per-step saga table.
- `audit.audit_events.request_json` stores logical operation parameters only: target IDs, intended state, operator context, and safe audit metadata. It never stores raw HTTP payloads, raw headers, or vendor request bodies.
- `audit.audit_events.error_text` stores a sanitized application-level summary only. Secrets, tokens, connection strings, raw headers, and raw tracebacks are scrubbed or truncated before persistence.

## 4. Applications subsystem

Application forms should be DB-stored, not YAML-backed in production. YAML remains useful as a bootstrap or import format, but it is not the system of record for a Railway-hosted workflow that needs versioning, auditability, and live chapter management. Each chapter's active form lives in `application_forms` plus immutable `application_form_versions`. A form edit creates a new version row; it never rewrites history.

The first operational dependency is explicit: Humility currently has no live chapters. Before Phase 1 starts, one staging chapter and any first production seed chapter needed for rollout must be manually bootstrapped from the existing template structure and inserted into `chapters`, `chapter_roles`, and `chapter_channels`. Applications do not pretend that chapter infrastructure already exists; they depend on that one-time bootstrap until automated provisioning ships later.

The preferred user surface is `/apply chapter:<chapter>`, with autocomplete limited to active, non-archived chapters. The slash command performs three checks before opening the first interaction: the chapter exists and is active, the applicant is not blacklisted for that chapter, and the applicant has no active application in `draft`, `submitted`, `claimed`, `interview`, or `waitlist`. The blacklist is checked again on final submit to close the race where staff blacklists the user while they are mid-flow.

Rendering uses Discord's current interaction components if the chosen library actually supports the required inputs. The logical form planner should support string input, numeric input, single-select, multi-select, radio, checkbox, and file upload components. The planner turns one form version into one or more interaction pages constrained by Discord limits. If a form fits inside one modal, it stays one modal. If it exceeds modal limits, the daemon uses a sequenced interaction session across later component interactions. The important rule is that the form model is logical and stable; the component plan is a derived rendering artifact stored alongside the version.

The component fallback is explicit, not a handwave. If hookpoint verification shows that the required Discord input components are not actually exposed through the chosen `discord.py` surface, richer web forms move into v1 as the replacement surface for the application intake workflow. That fallback uses the same `application_forms`, `application_form_versions`, and `applications` records. It does not reintroduce YAML as the source of truth, does not create a compatibility fork, and does not move officer review out of Discord. Discord remains the review, claim, decision, and audit surface either way.

On `/apply`, the daemon creates an `applications` row in `draft` with the target `application_form_version_id`, applicant ID, and empty answers. Each completed interaction page updates `answers_json`. Final submit transitions `draft -> submitted`, stamps `submitted_at`, and writes the immutable answer snapshot. This preserves abandoned starts and gives staff a truthful audit trail about whether a user opened the form and how far they got.

Once submitted, the daemon posts a review embed in the chapter applications queue and creates a private review thread in the same parent channel. The thread is created as a private thread, not a message-attached public thread. The queue message contains the chapter, applicant, submission time, current state, and a compact answer summary. Buttons are `Claim`, `Interview`, `Waitlist`, `Approve`, and `Deny`. The embed also links or mentions the private thread. The thread is seeded with the applicant, all chapter officers for that chapter, the bot itself, and any preserved central override users configured by policy.

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

The distinction between `interview` and `waitlist` must be operational, not cosmetic. `interview` means an officer is actively working the case and expects a follow-up conversation or extra evidence; the claimer remains the active owner. `waitlist` means the application is paused for capacity, timing, or chapter demand reasons; it is not approved and is not currently "in interview." When an application moves to `waitlist`, the daemon re-expands thread membership from the claimer-only set back to chapter officers so another officer can later pick it up without staff-side repair.

`Claim` uses the shared claim-visibility helper. On success, the application transitions to `claimed`, stores `claimed_by_discord_user_id`, and narrows the review thread to the applicant, the claimer, the bot, and any explicitly preserved override users. `Interview` transitions the record without changing the answer snapshot and posts the follow-up request in-thread.

`Approve` is a bounded mutation sequence, not raw Discord calls scattered through the handler. The daemon adds the chapter `member_role_id` and base `chapter_role_id`, removes the chapter `applicant_role_id`, inserts or updates the `chapter_members` row using the submitted in-game name, records the status transition, DMs the applicant with the outcome, posts a terminal embed in the thread, and archives the thread. The daemon does not auto-assign `guild_war_role_id`; that remains manual unless a later requirement justifies it.

`Deny` opens a short staff modal requiring a reason and allowing a `Blacklist this applicant for this chapter` checkbox. The reason is stored in both `applications.decision_reason` and `application_status_history.note`. If the checkbox is selected, the daemon inserts an `application_blacklist` row tied back to the application. The daemon DMs the applicant with the reason, marks the application denied, posts the denial in-thread, and archives the thread.

Retention is full. Nothing is hard-deleted. Old applications remain queryable forever. "Deleting" a queue message or archiving a thread is a Discord UX action, not data deletion. The DB record, status history, answer snapshot, and denial or waitlist notes remain intact.

## 5. Tickets subsystem

Tickets and applications should share the same queue, thread, and claim foundation, but they remain separate state machines and tables because their routing and terminal actions differ. The v1 ticket scope is intentionally narrow: only `server_support` ships.

Deferred ticket types are explicit:

- `chapter_support` and `chapter_incident` wait until real chapter infrastructure exists and there is real operator demand to route into it.
- `moderator` waits until the `Moderator` role is actually staffed.

The primary v1 open surface is one slash command plus one persistent panel in the existing global support surface: `/ticket open subject:<text> description:<text>`. The daemon writes the `tickets` row first, posts a queue embed second, and creates the private thread third. The queue message is the operator anchor; the thread holds the case conversation.

Claim mechanics are shared with applications. The common helper receives the thread, requester, claimer, and preserved-user set, then mutates explicit private-thread membership. It does not assume that role-based visibility alone is enough, because the goal is to narrow the case after claim.

Transcript persistence is simplified for v1. The daemon does not mirror every ticket-thread message in real time. Instead, on close it fetches the full thread history through the Discord API, paginates until complete, persists the normalized transcript into `ticket_messages`, then marks the ticket `closed` and archives the thread. At Humility's current ticket volume, this delivers the retention requirement with much less infrastructure than live mirroring plus reconciliation. If ticket volume later rises enough that close-time-only capture is no longer adequate, real-time transcript mirroring can be added as a future expansion rather than shipped speculatively in v1.

Close flow: the closer clicks `Close`, supplies a reason, the daemon persists the close record, fetches and stores the full thread history, posts a terminal summary, marks the ticket `closed`, edits the queue message to reflect closure, and archives the thread. Tickets are never hard-deleted.

If the requester leaves the server mid-ticket, the ticket remains valid. The daemon marks `requester_left_server_at`, updates the queue embed, and stops assuming the user can be re-added to the private thread. Staff can continue discussing and close the case. Any final DM attempt is best-effort and logged. A user leaving the guild is not a reason to lose the ticket record.

## 6. Activity tracking subsystem

The input surface is an officer-only slash command, not DM, and not "post images anywhere and hope the bot sees them." The core command is `/activity upload chapter:<chapter> date:<YYYY-MM-DD> image:<attachment>`. It is executable only by chapter officers for that chapter, `Staff`, or `Administrator`. The command can run from the chapter officer lobby or a global staff ops channel; the channel context is recorded, but the chapter argument is explicit so the upload is never inferred from channel name alone.

Roster binding is ongoing, not one-time. `chapter_members` is initially seeded from approved applications, but officers need explicit maintenance commands for roster corrections and late links: `/chapter roster link`, `/chapter roster rename`, `/chapter roster remove`, and `/chapter roster import` from a simple CSV attachment if needed. Activity tracking depends on a maintained `(chapter, in_game_name, discord_user_id)` mapping. The daemon should therefore treat roster quality as a first-class operational concern, not as an afterthought behind OCR.

The OCR subsystem is explicitly split into two deliverables.

### Phase 2a: upload, store, Vision, basic extraction

Phase 2a is the minimum useful ingestion path:

1. Receive the image through the slash command. Immediately copy the attachment into Supabase Storage, hash it, create the `activity_uploads` row in `received`, and acknowledge the interaction.
2. Run conservative preprocessing only when needed. V1 should support chapter-configurable crop rectangles, grayscale normalization, and contrast boost. More aggressive transforms are deferred until there is evidence they improve Humility screenshots.
3. Call Google Cloud Vision `DOCUMENT_TEXT_DETECTION` on the stored or preprocessed image.
4. Produce a basic row extraction using conservative heuristics that try to recover `(player_name, score)` pairs without yet claiming calibrated confidence. The goal of Phase 2a is durable ingestion and operator-visible extraction, not fully trusted automation.
5. Persist the upload record, provider payload, and extracted rows, and post an officer-visible summary that shows what was extracted and what still needs review.

Phase 2a is intentionally smaller than the full OCR ambition. It proves storage, provider integration, and basic parsing against real screenshots before the system grows confidence scoring, fallback logic, and rule automation.

### Phase 2b: confidence scoring, fallback, correction, rule evaluation

Phase 2b turns ingestion into a trustworthy operational workflow:

1. Add row confidence scoring derived from OCR token quality, row shape, numeric parse quality, and roster match quality.
2. Add the three-way routing decision: accept directly, flag for review, or escalate to Gemini.
3. Add Gemini 3 Flash Preview fallback for ambiguous uploads only, passing the original image plus classical OCR output and requiring strict JSON rows with quoted evidence.
4. Add hallucination controls. Fallback output is rejected when quoted text cannot be grounded in the classical OCR text, when row count diverges materially without explanation, or when scores violate chapter expectations.
5. Add Discord correction tools: `Link Member`, `Edit Score`, `Add Missing Row`, `Reject Row`, and `Confirm Upload`.
6. Add `activity_rules` evaluation and officer-visible flag posting.

No hardcoded OCR thresholds are presented as validated design truths. Any starter threshold values introduced during implementation are calibration inputs only and must be tuned against a retained Humility gold corpus before they are treated as operational defaults.

The rule language stays row-backed in the database, not YAML and not a free-form DSL. V1 only needs a compact grammar expressed by columns: metric, operator, threshold, window length, and required breach count. "Flag anyone under 50 points for 3 consecutive days" becomes `metric_name='points'`, `comparison_operator='lt'`, `threshold_value=50`, `window_days=3`, `breach_count_required=3`, `evaluation_mode='consecutive'`.

Flag output should post to the chapter officer lobby or designated activity review channel stored on the rule. DM is the wrong primary surface because activity management is a chapter workflow, not a private one-person workflow. Corrections create new `activity_log` versions by superseding the prior row; they do not overwrite history.

Historical backfill is allowed. Officers can upload an image with an explicit past `date:` value, and the daemon processes it normally. If a current row already exists for that member and day, the new corrected value supersedes the prior active row rather than deleting it.

## 7. Chapter provisioning subsystem

Chapter creation should still start from an admin-only slash command, not from the CLI. Provisioning is a visible-write workflow that benefits from inline preview, confirmation, progress updates, and audit linkage inside Discord where the operator already is. The CLI can still help inspect or validate state locally, but it is not the primary mutation trigger.

The entrypoint is `/chapters create spec:<attachment>`. The attachment is a YAML or JSON spec containing chapter name, slug, game, initial officers, form questions, activity rules, and any non-default channel options. This keeps the trigger to one command while still allowing structured nested input. YAML is acceptable as an operator input format here; it is not a production source of truth after import.

The first manual bootstrap dependency is explicit and separate from automation. Because Humility currently has no live chapters, one staging chapter and any first production seed chapter needed for rollout must be created manually from the existing `GUILD TEMPLATE` structure before Phase 1 or Phase 2 can operate against real chapter data. Phase 4 then automates subsequent chapter creation and makes later chapter setup repeatable.

The v1 automated create path is sequential and auditable, but intentionally lighter than the original saga:

1. Validate the spec and run a dry-run cap check.
2. Write `provisioning_runs.current_status='planned'` with the submitted spec and validation report.
3. Show the requester a preview and require an explicit `Confirm` button from an authorized admin before visible writes begin.
4. After confirmation, create the chapter resources in order while updating one `provisioning_runs` row with created Discord IDs and status.

The create flow runs these steps in order:

1. Create the six chapter-specific roles cloned from templates and renamed with the chapter prefix.
2. Create the chapter category with base overwrites.
3. Create the minimum v1 channels required for chapter operation, including the applications queue and officer lobby.
4. Apply channel-level overwrites explicitly to every created channel. The design does not rely on category inheritance alone because permission drift was one of the researched failure modes.
5. Write the `chapters`, `chapter_roles`, and `chapter_channels` rows to Postgres.
6. Insert the application form and first immutable form version.
7. Insert the initial activity rules.
8. Post the application panel in the chapter applications channel and pin it.

Each successful step records any created Discord IDs into `created_resources_json` on the run row as soon as they exist. That preserves auditability and gives operators a clean cleanup target if the run fails mid-way.

What v1 does not do is pretend Humility needs an enterprise-grade orchestration engine. There is no automatic resume-from-midpoint state machine and no generic reverse-ordered rollback framework. If a create run fails after creating some resources, the daemon marks the run `failed`, reports the failing step and the already-created resource IDs, and leaves the operator with an explicit cleanup path instead of hidden automation.

Cleanup is explicit and run-scoped. A follow-up admin action can use the recorded IDs from `created_resources_json` to archive or delete the resources created by that failed run, then mark the run `cleaned_up` with a `cleanup_report_json` summary. That keeps the operator in control and stays proportionate to Humility's expected chapter volume.

Role and category caps must still be checked before confirmation. The dry run should compute `current + projected` counts against Discord's hard caps and also enforce internal guardrails. A sensible v1 rule is to fail chapter creation when the resulting server would exceed 240 roles or 45 categories, leaving headroom for emergencies and future system roles rather than aiming for literal maximums.

Provisioning UX should be explicit. The requester sees an ephemeral validation summary immediately, then a progress message showing high-level completion with links to created resources as they become available. The final summary includes the created role IDs, channel IDs, and any warnings such as remaining role or category headroom.

## 8. Shared infrastructure

The claim-visibility helper should be a shared service used by both applications and tickets. Its interface should accept the thread ID, requester user ID, optional claimer user ID, the set of preclaim handler user IDs, and the set of preserved override user IDs, and return the before/after membership snapshot plus unresolved members. The helper owns thread membership reconciliation only. It does not own state-machine transitions.

Every visible Discord mutation should go through a mutation safety wrapper. The wrapper records a `planned` audit event before the mutation, executes exactly one bounded Discord API operation, captures the resulting safe snapshot or safe failure summary, and records a `succeeded`, `failed`, or `rolled_back` event after the operation.

Bounded mutation patterns are non-negotiable because the bot will operate with high privilege. Helpers must target one concrete object and one concrete intended change. Example: `add_role(member_id, role_id)` is acceptable; `sync_roles_for_all_members(chapter_id)` is not a v1 helper. `set_channel_overwrite(channel_id, target_role_id, overwrite_payload)` is acceptable; "clone all overwrites from category to every channel in the server" is not. The code should make bulk operations impossible by default and require explicitly enumerated targets even inside provisioning runs.

The mutation wrapper must also be Discord-rate-limit aware. It includes retry and backoff behavior that respects `Retry-After`, uses per-route or per-resource pacing for bursty paths, and avoids naive rapid retries. Provisioning, transcript-history fetches, and any reconciliation path that can issue many Discord calls in sequence must run through queued or paced execution rather than assuming the library will make rate-limit pressure irrelevant.

Audit and mutation payload boundaries are explicit:

- `request_json` stores logical operation parameters only: target IDs, intended state, safe operator context, and internal operation metadata.
- `request_json` never stores raw HTTP payloads, raw headers, raw Discord REST bodies, or vendor request bodies.
- `error_text` stores a sanitized application-level summary only.
- Secrets, tokens, headers, connection strings, and raw tracebacks are scrubbed or truncated before landing in audit rows or logs.

Background jobs should use Railway Cron for scheduled work rather than an in-process scheduler. The live daemon remains one process. Scheduled evaluation tasks such as long-wait reminders or periodic activity-rule recomputation should run as one-shot management commands in ephemeral Railway cron containers against the same repo and database.

## 9. Deployment

Dockerfile sketch: `python:3.12-slim` base, minimal system image packages for image preprocessing, pinned Python dependencies, source plus migrations copied in, Alembic run in a release step, entrypoint `python -m daemon`.

Railway service configuration:

- One always-on worker service for the daemon.
- Start command: `python -m daemon`.
- Release command: `alembic upgrade head`.
- Region: same region family as Supabase to minimize DB latency.
- Health check: expose a tiny in-process `/healthz` endpoint from the daemon that reports last gateway heartbeat, DB connectivity, and whether the bot is in a reconnect loop.

Supabase project layout:

- One production project and one staging project.
- Schemas: `app` for operational tables, `audit` for append-only audit history.
- Storage buckets: `activity-evidence` for screenshots.
- Row-level security: disabled on `app` and `audit` tables in v1 because only the trusted daemon service role uses them. If a future web app adds untrusted clients, introduce read models or views with RLS then rather than retrofitting it under time pressure.

Secrets management:

- Railway stores `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY`, `GOOGLE_CLOUD_VISION_KEY`, and `GEMINI_API_KEY`.
- The daemon reads secrets only from Railway environment variables in production.
- Local `.env` remains for development and the read-only CLI only.
- Structured log serialization and any log export path must pass through the same secret-scrubbing filter that protects `audit.audit_events.error_text`.

Migration tool: Alembic. The schema is relational, versioned, and expected to evolve under active development. Alembic is the least surprising migration tool in the Python/Postgres stack and fits the project's future direction better than ad hoc bootstrapping scripts.

Monorepo layout:

- `daemon/`: live Discord daemon package.
- `discord_cli.py`: sibling read-mostly inspection tool.
- `migrations/`: Alembic environment and SQL revisions.
- `forms/` and draft docs remain reference material only until hookpoint research decides what survives.
- `proposals/`, `research/`, `risk/`, and `docs/` remain planning artifacts.

## 10. Observability

Logs should be structured JSON to stdout so Railway captures them cleanly. Minimum fields: timestamp, severity, subsystem, guild ID, chapter ID when relevant, object IDs, OCR provider, audit operation name, and exception class.

Structured logs pass through a secret-scrubbing filter before serialization or export. That filter removes or masks secrets, tokens, authorization headers, connection strings, and similar sensitive values, and truncates raw tracebacks down to application-level context before any log line is emitted or any `error_text` field is persisted. The goal is durable observability without durable credential leakage.

Metrics should be exposed from the same lightweight health server as Prometheus-style counters and gauges. The important v1 metrics are:

- command invocations by command name and result
- active applications by state
- active tickets by state
- claim operations and failures
- OCR upload counts by outcome
- Google Vision latency and error rate
- Gemini escalation rate
- row confidence distribution once Phase 2b lands
- unmatched roster row count
- mutation wrapper failures by operation type
- Discord rate-limit retries by route family
- gateway reconnect count and current session age

Alerting should wake the owner for only the truly operational failures:

- daemon process down or stuck reconnecting
- Supabase DB connectivity lost for sustained duration
- migration failure on deploy
- Google Vision quota or auth failures causing all activity uploads to fail
- Gemini auth failure only if fallback is frequently needed
- mutation wrapper failure rate above a threshold for role or channel mutations
- sustained Discord rate-limit failures despite wrapper backoff

The blast radius boundaries should be strict. Activity tracking failures must not take down applications or tickets. OCR work should run in a bounded async task queue with timeouts and exception isolation. A failed OCR upload becomes a failed upload record and an officer-visible error message. It does not crash the gateway client or block unrelated interactions.

## 11. Testing strategy

Unit tests should cover the places where correctness can be decided without Discord: application and ticket state transitions, claim-membership planning logic, form-version rendering plans, activity row parsing, OCR escalation routing, activity-rule evaluation, provisioning dry-run validation, mutation-wrapper audit behavior, secret scrubbing, and rate-limit-aware retry behavior.

Integration tests should sit above unit tests and below a real Discord server. Discord API calls should sit behind narrow service helpers so tests can run against fake guild, channel, thread, and rate-limit responses. Transcript-close tests should verify that a close operation paginates the full thread history and persists normalized rows. Provisioning tests should verify that created-resource IDs are recorded incrementally and that explicit cleanup uses only recorded IDs rather than implicit discovery.

Staging should exist. The cleanest v1 choice is a separate staging Discord guild plus the staging Supabase project. A sandbox category inside the production Humility guild is not good enough for provisioning, permission, and role-cap tests because it cannot safely reproduce the real visible-write surface.

Manual first-deploy checklist:

- `/daemon-ping` responds.
- the one-time staging chapter bootstrap exists before applications or activity rollout.
- one chapter form opens and submits correctly through the Discord path, or through the approved web fallback if the Discord component surface is insufficient.
- review embed and private thread are created.
- claim narrows thread membership correctly.
- approve adds the intended roles and removes the applicant role.
- deny captures reason and optionally blacklists.
- one Phase 2a activity upload stores evidence and basic extraction.
- one Phase 2b ambiguous upload escalates to Gemini, lands in review, and supports row correction.
- one `server_support` ticket can be opened, claimed, closed, and persisted via close-time transcript fetch.
- one failed chapter provisioning run records created IDs, and one explicit cleanup cycle completes in staging.

OCR accuracy measurement needs a retained gold corpus. Before the subsystem is trusted, Humility should assemble a labeled screenshot set from its real games and scoreboards. The daemon then measures row precision, score accuracy, roster match rate, fallback rate, and human-correction rate. Ambiguous rows should be flagged, not guessed.

## 12. Sequencing plan

### Phase 0: foundations

Definition of done: Railway deploys a single daemon service, Supabase schema exists, Alembic is wired, structured logging is live, `/daemon-ping` works in staging and production, the mutation wrapper can write safe audit events, and the secret-scrubbing filter is active for both logs and persisted failures.

Demoable outcome: the owner can invoke `/daemon-ping`, inspect the live build version, and verify DB connectivity and health metrics.

Dependencies for next phase: stable Discord auth, stable DB connectivity, migrations, safe audit writes, and the mutation wrapper skeleton with rate-limit-aware execution.

### Phase 0.5: one-time manual chapter bootstrap

Definition of done: one staging chapter, and any first production seed chapter needed for rollout, exists manually with the minimum required roles and channels, and the matching `chapters`, `chapter_roles`, and `chapter_channels` rows are in Postgres.

Demoable outcome: applications and activity uploads have a real chapter target without waiting on provisioning automation.

Dependencies for next phase: validated template assumptions and a clean record of the manually created Discord IDs.

### Phase 1: applications

Definition of done: one active chapter has a working form, `/apply` opens the form, submissions persist, review embed plus private thread are created, officers can claim/interview/waitlist/approve/deny, approval mutates roles and roster rows, denial can blacklist, and DMs are sent when possible.

Demoable outcome: a staging applicant completes the full flow from slash command to approval and role assignment.

Dependencies for next phase: claim helper, audit logging for role mutations, stable thread handling, and confirmed applicant input surface. If the Discord component surface is insufficient, the narrow web-form fallback must be in place before this phase is considered done.

### Phase 2a: activity ingestion

Definition of done: officers can upload screenshots, evidence is stored durably, the Google Vision path works, basic row extraction persists to `activity_log`, and officers receive an extraction summary even when trust is not yet high enough for automation.

Demoable outcome: one real or staging screenshot is uploaded, stored, OCR'd, and rendered into a durable extraction summary.

Dependencies for next phase: storage integration, roster bindings from applications, and stable officer-channel posting.

### Phase 2b: activity automation

Definition of done: confidence scoring, Gemini fallback, manual correction UI, and rule evaluation are live, and ambiguous uploads are flagged rather than silently accepted.

Demoable outcome: one low-confidence screenshot escalates, passes grounded validation, and results in a correctable officer review flow plus rule-based flag output.

Dependencies for next phase: retained evaluation corpus, calibrated thresholds, and reliable review-thread or review-message actions.

### Phase 3: tickets

Definition of done: `server_support` tickets can be opened, routed, claimed, transcripted at close time, and closed with full retention.

Demoable outcome: a member opens a support ticket, staff claims it, the case thread is closed, and the full transcript lands in `ticket_messages`.

Dependencies for next phase: shared claim helper, queue/thread infrastructure, and stable close-time full-history fetch.

### Phase 4: chapter provisioning automation

Definition of done: an admin can submit a chapter spec, receive a dry-run preview, confirm creation, watch progress, and end with a fully provisioned chapter including roles, channels, form, activity rules, and application panel. If a run fails, the created resource IDs are recorded and can drive an explicit cleanup action.

Demoable outcome: a new staging chapter appears end to end from one confirmed provisioning run, and one failed run can be cleaned up explicitly using the recorded IDs.

Dependencies: everything earlier. Provisioning consumes the form engine, activity-rule model, mutation wrapper, audit system, and validated chapter template assumptions. It should not land before those subsystems exist for real.

## 13. Rollback plan

Phase 0 rollback is redeploying the prior Railway image and, if needed, rolling back to the previous Alembic revision only when the newer schema is not yet in use. Because this is the foundation phase, DB rollback should be treated cautiously and only for clearly reversible migrations.

Phase 0.5 rollback is manual because the bootstrap is manual. If the seed chapter setup is wrong, correct or recreate that specific bootstrap chapter before later phases depend on it. The proposal does not pretend that the first bootstrap is automated.

Phase 1 rollback is redeploying the previous daemon image and disabling the application slash command and panel if needed. Existing application data remains in Postgres. If a role-mutation bug appears, corrective role removals are executed through the same bounded mutation wrapper with audit events, not through ad hoc scripts.

Phase 2a rollback is disabling `/activity upload` while leaving all stored evidence and extracted rows intact. Phase 2b rollback is disabling fallback, correction buttons, and rule evaluation while preserving the underlying uploads and row data.

Phase 3 rollback is disabling the ticket panel and slash command, then leaving already-open tickets readable while staff closes them manually. Transcript data already captured at close remains.

Phase 4 rollback is explicit cleanup, not hidden orchestration. If a create run fails, the operator reviews `created_resources_json`, then runs the specific cleanup action for that run or performs the equivalent manual cleanup using the recorded IDs. Cleanup archives or deletes created resources as appropriate for that exact run and records the result in `cleanup_report_json`.

## 14. Anti-scope (explicitly out of v1)

- `chapter_support` and `chapter_incident` tickets. They wait until chapters exist and there is real demand to route into them.
- `moderator` tickets. They wait until the `Moderator` role is actually staffed.
- Full moderation system. Research and decisions explicitly put moderation outside the first build.
- Real-time ticket transcript mirroring plus reconciliation. V1 uses close-time full-history fetch only.
- Automatic provisioning resume engines and generic rollback orchestration. V1 records created IDs and uses explicit cleanup instead.
- General web reviewer dashboards. Discord is the operator surface in v1. The only web surface that may enter v1 is the narrow application-form fallback if required Discord components are unavailable through `discord.py`.
- Multi-guild tenancy. The daemon is for Humility guild `<guild id>`, not a generic SaaS.
- SQLite or local-first fallback. Postgres is the system of record.
- YAML as the production source of truth. YAML may be used as import or operator input only.
- Compatibility shims, dual-write paths, feature flags for old behavior, or other transitional support layers.
- Hardcoded OCR acceptance thresholds presented as settled design truths. Thresholds are calibration inputs validated against retained screenshot evidence.
- Automatic punishments or kicks from activity rules. V1 flags members for officer review; it does not auto-enforce.
- Spreadsheet sync. The goal is to replace the manual spreadsheet workflow, not keep two systems in parallel.

## 15. Risks and mitigations

- Secret leakage into audit rows or logs. Mitigation: `request_json` is logical-parameters only, `error_text` is sanitized before persistence, and structured logs pass through the same secret-scrubbing filter before emission or export.
- Discord rate-limit pressure during provisioning or transcript fetch. Mitigation: all visible writes and bursty fetch paths use the mutation wrapper with `Retry-After` respect, paced execution, and per-route retry/backoff rather than ad hoc retries.
- OCR accuracy risk. Mitigation: split the subsystem into 2a and 2b, keep Google Vision as the primary deterministic layer, calibrate any thresholds against a retained gold corpus, and flag ambiguity instead of guessing.
- Player-to-Discord identity mapping risk. Mitigation: make `chapter_members` and roster linking explicit, seed from approved applications, and treat unmatched rows as review-required rather than auto-linked guesses.
- Discord component support risk for applications. Mitigation: verify the actual `discord.py` surface during hookpoint work, and if required components are missing, move applicant input to the scoped web fallback in v1 instead of shipping degraded text-only forms.
- Manual bootstrap dependency risk. Mitigation: make the seed chapter setup explicit in sequencing, keep the bootstrap narrow, and record the created Discord IDs before later phases rely on them.
- Role and category cap growth. Mitigation: dry-run cap checks with internal guardrails below Discord hard limits, and keep v1 ticket scope narrow so provisioning does not create unnecessary per-chapter queues.
- Permission drift over time. Mitigation: channel overwrites are applied explicitly by provisioning, audited, and later inspectable via `discord_cli.py`; do not rely on category inheritance staying correct forever.
- Bounded-mutation bug while the bot has Administrator. Mitigation: all visible writes go through one wrapper, helper interfaces only accept concrete targets, and no bulk mutation helper is exposed in v1.
- Ticket transcript loss before close. Mitigation: keep ordinary handlers from deleting ticket threads, fetch full history before archive on close, and accept that close-time capture is proportionate at Humility's current ticket volume.
- Requester leaves the server mid-ticket or application. Mitigation: treat Discord membership as mutable but keep durable user IDs and records; closure and audit do not depend on the user still being present.

## 16. Open questions for hookpoint phase

- Which pieces of the existing `daemon/` draft are worth preserving as implementation hookpoints, especially the current config loader, claim helper, and application review view?
- What is the thinnest acceptable operator path for editing DB-backed application forms after initial bootstrap and provisioning, without reintroducing YAML as the source of truth?
- Does `discord.py 2.7.1` expose every required application input component through stable APIs, and if not, what is the cleanest narrow web-form fallback that preserves the same contracts and review flow?
- What is the exact meaning of the six chapter template roles in Humility's live guild, especially the distinction between `Chapter`, `Chapter Public`, and `Chapter Member`?
- Should activity review posts live in each chapter officer lobby or in one global staff-ops review channel with chapter tagging?
- Is there any historical data worth importing from Gather or ticket exports before v1 goes live?
- What is the right staging guild topology so provisioning, role hierarchy, and application review permissions can be tested without production risk?

## 17. Cost model

Assumptions:

- one always-on Railway worker
- one production Supabase project, one staging project
- low MVP volume: roughly 150 to 600 activity screenshots per month
- Google Vision used on all uploads
- Gemini used only on a minority of ambiguous uploads after Phase 2b
- no second always-on service in v1

Estimated monthly cost:

- Railway: about `$5-10/month` for one small always-on service.
- Supabase: production should be budgeted as paid once the daemon becomes the operational system of record; assume about `$25/month` for prod, with staging on free.
- Google Cloud Vision: effectively `$0/month` under the first 1,000 images, and still likely only `$0-2/month` at MVP volume.
- Gemini 3 Flash Preview fallback: about `$1/month` at MVP volume if fallback stays rare.

Recommended operating total: about `$31-38/month`.

Cheapest plausible early total if production remains on free tier briefly: about `$6-13/month`.

The simplified ticket and provisioning scopes reduce engineering burden more than they reduce hosting spend. The cost model is still dominated by hosting and database choices, not by OCR. That supports the proposal's choice to optimize for operational correctness, retention, and safe automation rather than over-optimizing per-image spend.
