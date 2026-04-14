# Proposal: `services/api/app/contracts/chapters.py`

Date: 2026-04-13

## Goal

Define `services/api/app/contracts/chapters.py` as the Pydantic contract
module for chapter CRUD operations at the API boundary.

The module should introduce exactly four public contract symbols:

- `ChapterStatus`
- `ChapterCreate`
- `ChapterRead`
- `ChapterUpdate`

This proposal is design only. It does not include implementation code.

## Architecture

`chapters.py` should sit beside `base.py` inside
`services/api/app/contracts/` and follow the package contract described
in [services/api/app/contracts/__init__.py](/home/nes/discord/services/api/app/contracts/__init__.py:1):
these models are the external API surface, not internal repository or
service types.

Ownership split:

- `base.py` continues to own shared contract mixins, specifically
  `VersionedMixin`.
- `chapters.py` owns only chapter CRUD request/response schemas and the
  chapter lifecycle enum.
- Services and repositories remain responsible for stale-write
  detection, uniqueness checks, state-machine rules, and persistence.

`ChapterRead` and `ChapterUpdate` should reuse `VersionedMixin` rather
than redefining `version`, so optimistic locking stays consistent across
contract modules. `ChapterCreate` must not inherit it.

The module should be narrowly composable: later form-, membership-, or
chapter-settings contracts can reference these chapter schemas or the
chapter ID, but should not replace this module or embed unrelated
collections into it.

## Proposed Module Surface

### `ChapterStatus`

Use a `StrEnum` with exactly these values:

- `active`
- `archived`
- `provisioning`

Rationale:

- It gives the API a closed lifecycle vocabulary.
- It produces string enum values in OpenAPI instead of integer-backed
  enums.
- It prevents arbitrary status strings from leaking into service logic.

### `ChapterCreate(BaseModel)`

Purpose: create-request body for a new chapter record.

Fields:

| Field | Type | Required | Constraints | Notes |
|---|---|---|---|---|
| `name` | `str` | yes | min length `1`, max length `100` | Trim leading/trailing whitespace before validation. Whitespace-only input is invalid after trimming. |
| `slug` | `str` | yes | max length `50`, regex `^[a-z0-9]+(?:-[a-z0-9]+)*$` | Lowercase ASCII slug. Reject invalid input rather than normalizing it. |

Excluded from this model:

- `id`
- `version`
- `status`
- `discord_category_id`
- `discord_officer_role_id`
- `discord_member_role_id`
- `created_at`

This keeps create contracts limited to client-supplied chapter identity
fields. Server-assigned lifecycle and Discord resource fields do not
belong in the create body.

### `ChapterRead(VersionedMixin)`

Purpose: read/response model for a persisted chapter.

Fields:

| Field | Type | Required | Constraints | Notes |
|---|---|---|---|---|
| `id` | `int` | yes | positive integer | Server-assigned primary key. |
| `name` | `str` | yes | min length `1`, max length `100` | Same normalization/shape as create. |
| `slug` | `str` | yes | max length `50`, regex `^[a-z0-9]+(?:-[a-z0-9]+)*$` | Same shape as create. |
| `status` | `ChapterStatus` | yes | enum | Current lifecycle state. |
| `discord_category_id` | `int \| None` | yes | `> 0` when present | `None` is valid while provisioning or before reconciliation. |
| `discord_officer_role_id` | `int \| None` | yes | `> 0` when present | Discord snowflake stored as Python integer. |
| `discord_member_role_id` | `int \| None` | yes | `> 0` when present | Discord snowflake stored as Python integer. |
| `created_at` | `datetime` | yes | valid datetime | Server-assigned creation timestamp. |
| `version` | inherited from `VersionedMixin` | yes | integer, `>= 0` | Optimistic-lock version returned to clients. |

`ChapterRead` is the canonical persisted-state shape. It should include
all chapter record fields needed by API consumers and no write-only
helpers.

### `ChapterUpdate(VersionedMixin)`

Purpose: PATCH-style update body for mutable chapter fields.

Fields:

| Field | Type | Required | Constraints | Notes |
|---|---|---|---|---|
| `name` | `str \| None` | no | min length `1`, max length `100` when present | Patch-optional field. Omit to leave unchanged. |
| `slug` | `str \| None` | no | max length `50`, regex `^[a-z0-9]+(?:-[a-z0-9]+)*$` when present | Patch-optional field. |
| `status` | `ChapterStatus \| None` | no | enum when present | Patch-optional field. |
| `discord_category_id` | `int \| None` | no | `> 0` when present | Supports unset, set, and explicit clear semantics. |
| `discord_officer_role_id` | `int \| None` | no | `> 0` when present | Supports unset, set, and explicit clear semantics. |
| `discord_member_role_id` | `int \| None` | no | `> 0` when present | Supports unset, set, and explicit clear semantics. |
| `version` | inherited from `VersionedMixin` | yes | integer, `>= 0` | Required for optimistic locking. |

Update-model behavior:

- The model is patch-shaped, not replacement-shaped.
- Mutable fields default to omitted/optional at the request boundary.
- `version` remains required even though the rest of the body is patch
  optional.

Boundary rule:

- The contract preserves omission vs explicit `null` through Pydantic’s
  unset tracking.
- Services should use `exclude_unset=True` or `model_fields_set` when
  deciding which fields to mutate.

This is especially important for Discord IDs, where “do not touch” and
“clear the stored snowflake” must stay distinguishable.

## Validation Strategy

### Shared string rules

Apply the same field-level constraints to `name` and `slug` across read
and write models so the OpenAPI surface stays internally consistent.

For `name`:

- trim leading and trailing whitespace before length checks
- require non-empty content after trimming
- enforce max length `100`

For `slug`:

- require lowercase ASCII letters and digits with internal hyphens only
- enforce regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`
- enforce max length `50`
- reject uppercase or malformed values instead of coercing them

### Snowflake positivity

For `discord_category_id`, `discord_officer_role_id`, and
`discord_member_role_id`:

- represent them as Python `int`
- allow `None`
- require `> 0` whenever a value is present

This matches current Python-side repo convention while keeping the
contract honest about nullable provisioning state.

### Version validation

`version` should continue to come entirely from `VersionedMixin`:

- required on `ChapterRead`
- required on `ChapterUpdate`
- absent from `ChapterCreate`

The contract validates only presence and basic numeric bounds. Stale
write detection remains a service-layer concern and should still map to
`409 Conflict`.

### What this module should not validate

These checks do not belong in the contract module:

- slug uniqueness
- chapter name uniqueness
- whether a referenced Discord snowflake exists
- whether a status transition is allowed
- whether an archived chapter may be edited
- whether provisioning has completed

Those are business or persistence rules, not schema-boundary rules.

## OpenAPI Considerations

Separate create/read/update models are required for accurate generated
schema:

- `ChapterCreate` should show only client-supplied inputs.
- `ChapterRead` should show server-assigned fields and optimistic-lock
  state.
- `ChapterUpdate` should show patch semantics with a required
  `version`.

Enum considerations:

- `ChapterStatus` should render as a string enum with exactly three
  allowed values.

Datetime considerations:

- `created_at` should render as an OpenAPI `string` with `date-time`
  format.

Patch-schema considerations:

- Because patch fields are typed as `T | None`, OpenAPI will describe
  them as nullable optional fields.
- API consumers should omit fields they do not intend to change.
- Server code must distinguish omitted fields from explicitly sent
  `null` values during update handling.

Snowflake considerations:

- Keeping Discord IDs as JSON numbers matches current Python-side
  convention.
- This carries a known precision risk for JavaScript clients once values
  exceed `2^53 - 1`.
- That serialization concern should be handled at the API/shared-types
  boundary later rather than by widening this contract module now.

## Anti-Scope

The following do not belong in `services/api/app/contracts/chapters.py`:

- service methods or repository types
- database table definitions or Alembic concerns
- optimistic-lock conflict handling logic
- audit metadata such as `created_by`, `updated_by`, or `updated_at`
- list/search/filter/pagination response models
- nested form, roster, activity-rule, or Discord channel/role detail
  collections
- Discord provisioning workflows or template-cloning behavior
- package-wide re-export strategy outside the chapter module itself

This module should stay focused on the chapter record’s CRUD boundary
shape only.
