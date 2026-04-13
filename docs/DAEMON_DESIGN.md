# Daemon design

One long-running Python process (`daemon.py`), hosted on Railway, using
`discord.py` with a persistent gateway connection. SQLite for state on a
Railway persistent volume. YAML config files in the repo.

## Files

```
daemon.py                 # entry point: boot, load config, register handlers
daemon/
  config.py               # load chapters.yaml + forms/*.yaml
  db.py                   # SQLite schema, migrations, query helpers
  claim.py                # shared claim-visibility logic (threads + channels)
  applications.py         # form rendering, modal handling, submission flow
  tickets.py              # ticket flow (server, mod, chapter-variants)
  chapters.py             # provisioning: clone GUILD TEMPLATE per chapter
  util.py                 # helpers
chapters.yaml             # registry of active chapters
forms/*.yaml              # one per chapter (dark-nemesis.yaml, etc.)
```

## Channel & thread model

**Private threads** off queue messages, not per-item channels. Avoids
Discord's 500-channel cap, makes auto-archive free, and private-thread
membership is exactly the "claim" primitive we need.

### Global ticket queues (new "Staff Ops" category, hidden from @everyone)

- `#server-tickets` — visible to `⚔️ Staff`. Threads for server support tickets.
- `#mod-tickets` — visible to `⚔️ Moderator` (write) and `⚔️ Trial Mod` (read-only).

### Per chapter (extending the cloned template category)

- Existing template channels: events, guides, lobby, guild-lobby, officer-lobby, applications
- `#<chapter>-tickets` — chapter support, visible to `<Chapter> Officer`
- `#<chapter>-incidents` — in-game moderation incidents, visible to `<Chapter> Officer`
- The existing `#applications` queue channel becomes this chapter's application queue.

### Per-item flow (tickets and applications both)

1. User triggers `/apply <chapter>` or `/ticket <category>` (or clicks a panel button)
2. For applications: bot opens a modal, collects answers
3. Bot posts a queue message with embed (summary + answers for applications, or description for tickets)
4. Bot creates a **private thread** off that message
5. Bot adds the requester + every member of the handler role to the thread
6. Queue message carries buttons: **Claim**, **Close**, and for applications: **Approve**, **Deny**, **Interview**
7. **Claim** → bot removes everyone except claimer, requester, admins from the thread; marks queue message "Claimed by @X"
8. **Approve** (applications only) → role mutation per `on_accept` rules; DM applicant; archive thread
9. **Deny** → reason captured; DM applicant; archive thread
10. **Close** (tickets) → archive thread; log to a log channel

### Trial Mod read-only

The parent channel `#mod-tickets` has overwrites: `Trial Mod` allow
`VIEW_CHANNEL` + `READ_MESSAGE_HISTORY`, deny `SEND_MESSAGES`. Threads
inherit send permissions from the parent channel, so Trial Mod gets
read-only on all mod ticket threads automatically.

## Chapter provisioning (`chapters create <slug>`)

Runs as a daemon-side command triggered via the CLI. Sequence:

1. Clone the `GUILD TEMPLATE` category: create a new category `<Chapter Name>` with the same overwrites but targeted at the newly-minted chapter-specific roles.
2. Create chapter-specific roles by cloning each of the 6 template roles (`Chapter Officer`, `Chapter Member`, `Chapter Applicant`, `Chapter`, `Chapter Guild War`, `Chapter Public`) with the chapter slug prefixed.
3. Clone each text/voice channel from the template into the new category with matching overwrites.
4. Create the two additional chapter queue channels (`#<chapter>-tickets`, `#<chapter>-incidents`) visible only to `<Chapter> Officer`.
5. Register the chapter in `chapters.yaml` and associate the form at `forms/<slug>.yaml`.
6. Post an "Apply to <Chapter>" panel message in the #applications channel with a button that invokes `/apply <chapter>`.
7. Persist chapter metadata to the SQLite `chapters` table.

A chapter archive command reverses steps 1, 3, 4 (move channels to an
archive category or delete, with confirmation) and removes from
`chapters.yaml`.

## Blacklist

Per-chapter user-ID blacklist stored in SQLite. Checked at the top of
`/apply` — blocked users get an ephemeral "You cannot apply to this
chapter" message. Staff command `/chapter-blacklist add @user reason`
mutates the table.

## Form question types (v1)

Discord modals support up to 5 components per modal and the component types
are limited to `short` and `paragraph` text inputs. That means:

- `short`, `long` → native text inputs in the modal
- `select`, `multi_select` → **not supported in modals**. Handled by
  opening a follow-up ephemeral message with select menus after modal submit.
- `number` → text input with numeric validation server-side

Forms with more than 5 fields are split across multiple steps:
modal → select menus → modal → etc. The Dark Nemesis form has 7
questions (ign/short, timezone/select, daily_events/multi_select,
hours/number, budget_launch/number, budget_monthly/number,
experience/long). Split: modal#1 = [ign, hours, budget_launch,
budget_monthly, experience], follow-up ephemeral = [timezone select,
daily_events multi-select]. Final submit happens when the last menu is
answered.

## SQLite schema

```sql
CREATE TABLE chapters (
    slug TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    officer_role_id INTEGER NOT NULL,
    member_role_id INTEGER NOT NULL,
    applicant_role_id INTEGER NOT NULL,
    applications_channel_id INTEGER NOT NULL,
    tickets_channel_id INTEGER NOT NULL,
    incidents_channel_id INTEGER NOT NULL,
    form_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_id TEXT NOT NULL,
    chapter_slug TEXT NOT NULL,
    applicant_id INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL,      -- pending|claimed|interview|approved|denied|withdrawn
    queue_message_id INTEGER,
    queue_channel_id INTEGER,
    thread_id INTEGER,
    claimer_id INTEGER,
    decided_by INTEGER,
    decided_at TEXT,
    decision_reason TEXT,
    answers_json TEXT NOT NULL
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_type TEXT NOT NULL,   -- server|mod|chapter_support|chapter_incident
    chapter_slug TEXT,           -- null for server/mod tickets
    requester_id INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    status TEXT NOT NULL,        -- open|claimed|closed
    queue_message_id INTEGER,
    queue_channel_id INTEGER,
    thread_id INTEGER,
    claimer_id INTEGER,
    closed_at TEXT,
    closed_by INTEGER,
    subject TEXT,
    initial_description TEXT
);

CREATE TABLE chapter_blacklist (
    chapter_slug TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    added_by INTEGER NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (chapter_slug, user_id)
);
```

## Hosting

**Railway** (user already has an account):

- `Dockerfile` with Python 3.12 slim, uv, copy repo, `ENTRYPOINT ["uv", "run", "python", "daemon.py"]`
- `railway.toml` declares: build method, start command, health check (bot sends a gateway heartbeat — if the process dies, Railway restarts it)
- **Persistent volume** mounted at `/data` for `discord.db` (SQLite)
- Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DATABASE_PATH=/data/discord.db`
- Free tier is $5/mo credit, this bot will use a fraction of that

Cheap alternatives if Railway doesn't work out:
- **Fly.io**: 256 MB VM free, small volume, always-on
- **Oracle Cloud free tier**: 4 ARM vCPUs + 24 GB RAM forever free (but setup is more involved)
- **Hetzner CX22**: €3.29/mo (best price/perf if willing to manage a VPS)

Starting with Railway; migration is one Dockerfile + env var copy away.

## Deployment workflow

1. Developer (me) edits code/YAML in this repo
2. `git push` to Railway-watched repo
3. Railway auto-rebuilds and restarts the daemon
4. Bot reconnects to gateway, reloads config from YAML, resumes

No zero-downtime machinery needed for v1 — restart time is ~15s.

## What the CLI still does

`discord_cli.py` stays the inspection/one-shot interface. New
inspection commands get added as needed. The **daemon** handles all
interactions (slash commands, buttons, modals). The **CLI** handles
administrative one-shots (list submissions, force-mutate a role, post
a panel, run chapter provisioning). They share the SQLite database.
