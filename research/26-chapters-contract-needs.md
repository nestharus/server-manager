# Synthesis — Chapter contracts needs

Source: `research/26-chapters-contract.md`

## Humility-specific context

Chapters are the top-level organizational unit in Humility. Each
chapter gets its own Discord category (cloned from GUILD TEMPLATE),
roles (officer, member, guild war, applicant, public), forms, activity
rules, and member roster. Chapters are long-lived administrative
records with `active`, `archived`, and `provisioning` lifecycle states.

## Needs mapped from research

### 1. Separate CRUD contracts

Research confirms separate models for Create, Read, Update/Patch:
- **ChapterCreate**: client-supplied fields only (name, slug)
- **ChapterRead**: all fields including server-assigned (id, created_at,
  version, Discord IDs, status)
- **ChapterUpdate**: mutable fields + version for optimistic locking

### 2. VersionedMixin integration

Per existing `VersionedMixin` docstring and java-interview-setup:
- ChapterRead includes VersionedMixin (version exposed on reads)
- ChapterUpdate includes VersionedMixin (version required for stale
  detection)
- ChapterCreate does NOT include VersionedMixin

### 3. Field validation

- **name**: `str`, `min_length=1`, `max_length=100`, stripped whitespace
- **slug**: `str`, regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`, `max_length=50`
- **discord_category_id**: `int | None`, `gt=0` when present
  (None during provisioning)
- **discord_officer_role_id**: `int | None`, `gt=0` when present
- **discord_member_role_id**: `int | None`, `gt=0` when present
- **status**: `ChapterStatus` enum — `active`, `archived`, `provisioning`
- **id**: `int` (server-assigned, read-only)
- **created_at**: `datetime` (server-assigned, read-only)

### 4. ChapterStatus enum

A `StrEnum` or `str, Enum` for clean OpenAPI generation:
- `active` — normal operational state
- `archived` — retired, read-only
- `provisioning` — being set up, not yet ready

### 5. Composability

The task description says to "produce a clean Pydantic contract module
rooted in `VersionedMixin`, sized so later form-related contracts can
compose onto it rather than replace it." This means:
- Keep chapter contracts focused on chapter identity and lifecycle
- Form contracts will reference chapters by ID, not embed forms in
  chapter contracts
- The module should export clean, composable schemas

### 6. Gaps

- **Snowflake precision**: Research flags that Discord snowflake IDs as
  JSON numbers may cause precision loss in JavaScript clients (>2^53).
  For now, follow existing repo convention (Python int). Address at the
  serialization layer when the web frontend is built.
- **Audit fields**: Research confirms audit metadata (created_by,
  updated_by, updated_at) is server-managed, not client-supplied. Not
  needed in these contracts per the java-interview-setup pattern.

## Contract summary

File: `services/api/app/contracts/chapters.py`

Exports:
- `ChapterStatus` — StrEnum with active/archived/provisioning
- `ChapterCreate` — name + slug (create-only fields)
- `ChapterRead` — all fields including VersionedMixin
- `ChapterUpdate` — mutable fields + VersionedMixin
