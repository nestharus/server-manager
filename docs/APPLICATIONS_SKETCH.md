# Applications subsystem — sketch

Status: **design draft, not implemented.** Pending owner review.

## Goal

Replace Gather with a self-hosted guild-application flow that lives
inside this repo, so:

- Application forms are **code** (YAML/JSON in this repo), versioned, reviewable, diffable.
- The agent (Claude) can read and modify forms on request, without
  needing access to a third-party web dashboard.
- Submission history and reviewer decisions are stored locally (SQLite).
- No external SaaS dependency.

## Architecture

### 1. Persistent daemon (new)

The existing `discord_cli.py` is a "run once, exit" CLI. Interaction
handling (buttons, modals, slash commands) requires a **persistent
gateway connection**, because Discord delivers interaction events over
the gateway and the bot must respond within 3 seconds.

Solution: a new long-running process, e.g. `discord_daemon.py`, that:

- Connects to the gateway and stays online.
- Loads form definitions from `forms/*.yaml` at startup (and on a
  `reload` command).
- Registers per-form slash commands (e.g. `/apply chapter-membership`).
- Handles button clicks on "Submit application" and "Approve/Reject"
  panels.
- Persists submissions to a SQLite database.
- Posts notifications to a staff review channel.

Deployment: runs locally (wsl/linux host); managed by `systemd --user`
or just a `tmux`/`screen` session; logs to a file. No HTTP endpoint,
no public exposure — pure gateway.

### 2. Form definitions

`forms/chapter-membership.yaml` (example):

```yaml
id: chapter-membership
title: Chapter Membership Application
description: Apply to join a chapter.
review_channel_id: 960634532653060145   # admin-chat, placeholder
reviewer_role_ids:
  - 960634531210223668   # Chapter Officer
on_accept:
  remove_roles: [<Guest id>]
  add_roles:    [<Chapter Applicant id>]
  send_dm: "Welcome! An officer will onboard you shortly."
on_reject:
  send_dm: "Thanks for applying. We are not accepting at this time."
questions:
  - id: ign
    type: short
    label: In-game name
    required: true
    max_length: 32
  - id: timezone
    type: short
    label: Timezone
    required: true
  - id: experience
    type: long
    label: Briefly describe your prior guild experience
    required: true
    max_length: 1000
  - id: availability
    type: choice
    label: How active are you?
    choices:
      - Daily
      - Few times a week
      - Weekly
      - Rarely
```

Supported question types (v1):
- `short` — single-line text (Discord text input, 1–100 chars)
- `long`  — paragraph text (Discord text input, 1–4000 chars)
- `choice` — Discord select menu (one-of-N)

Deferred (v2):
- `multi` — multi-select from a list
- `number`, `boolean`
- `upload` — attachment
- Conditional / branching questions

Constraint: Discord **modals** support max 5 components per modal. For
forms longer than 5 questions, we'll submit in chunks (a "Next >" button
between modal pages) — or we break it into a thread-based interview. The
MVP spec should target ≤5 questions per form.

### 3. User flow

1. User runs `/apply chapter-membership` (or clicks a button on an
   application panel message the bot has posted).
2. Bot opens a **modal** with the form's questions.
3. User fills in and submits.
4. Bot stores submission in SQLite, assigns a `submission_id`, posts a
   message in the review channel with:
   - An embed containing the answers
   - Two buttons: **Approve** / **Reject**
   - A button to **Request more info** (creates a private thread with
     applicant + reviewers)
5. Reviewer with matching role clicks Approve/Reject.
6. Bot applies `on_accept` / `on_reject` actions and updates the
   submission row.
7. Bot DMs the applicant their result.

### 4. Persistence schema (SQLite)

```sql
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY,
    form_id TEXT NOT NULL,
    applicant_id INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,          -- pending | accepted | rejected | withdrawn
    review_message_id INTEGER,
    review_channel_id INTEGER,
    reviewer_id INTEGER,
    reviewed_at TEXT,
    answers_json TEXT NOT NULL     -- {"ign": "...", "timezone": "..."}
);

CREATE INDEX ix_submissions_form_status ON submissions(form_id, status);
CREATE INDEX ix_submissions_applicant   ON submissions(applicant_id);
```

### 5. CLI integration

New subcommands in `discord_cli.py` (still one-shot, operate against the
same SQLite file the daemon writes to):

- `forms list` — list known form ids
- `forms show <id>` — pretty-print a form
- `forms post-panel <id> <channel_id>` — post a permanent "Apply here"
  button panel in a channel
- `submissions list [--form <id>] [--status <s>]` — recent submissions
- `submissions show <id>` — full details
- `submissions export [--since <date>] [--csv path]` — dump history
- `daemon status` — check whether the daemon process is running
- `daemon reload` — tell the running daemon to reload forms (via a
  sentinel file or a bot-to-self DM)

### 6. Interaction with the chapter system

This subsystem does **not** create channels or clone the GUILD TEMPLATE
category. That's a separate concern. It only handles: "gather structured
information from a prospective member and grant/revoke roles based on a
reviewer decision."

A follow-up subsystem — call it `chapters` — could handle:
- `chapters create <slug>` — clone GUILD TEMPLATE category and
  associated roles for a new chapter.
- `chapters archive <slug>` — close a chapter and archive its channels.

Designing the chapters subsystem requires understanding how chapter
creation currently works (or is intended to work), which we don't
fully know yet.

## Open questions for the owner

1. **Form content**: what questions does the current Gather form actually
   ask? Can you either screenshot the form from the gather.sh dashboard
   or paraphrase the fields?
2. **Who reviews applications today?** Just you? The Chapter Officer
   role? A dedicated committee?
3. **Chapter creation**: when you want a new chapter, do you currently
   (a) clone the GUILD TEMPLATE category manually in Discord, (b) run a
   Gather flow that triggers channel creation, or (c) something else?
4. **Chapter roles**: when a new chapter is created, do new chapter-
   specific roles get created (e.g. "Dawn Chapter Member"), or does
   everyone share the existing `Chapter Member` role regardless of
   which chapter they're in?
5. **Storage location**: SQLite on disk is easy and private but not
   backed up. Alternative: store submissions as messages in a
   hidden #applications-log channel (survives host reinstall, visible
   in Discord, searchable). Preference?
6. **Daemon lifecycle**: who starts/stops the daemon? User-run systemd
   service? Or a `uv run discord_daemon.py` in a `tmux` session?
7. **Scope for this first pass**: build full Approve/Reject flow with
   role mutation, or start with "capture and notify" (form → review
   channel, reviewer manually adjusts roles) and add automation later?

Recommendation: start with **"capture and notify" only**, no automated
role mutation. Fastest to ship, lowest blast radius, and adequate for a
server that currently has zero in-flight applications. Automated role
mutation can come in a v2.
