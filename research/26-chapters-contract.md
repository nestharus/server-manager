# Research: Chapter CRUD Contracts (`services/api/app/contracts/chapters.py`)

Date: 2026-04-13

## Scope

This note documents the design space for chapter CRUD contracts at the
FastAPI/Pydantic boundary for the Humility API.

It is limited to:

- Pydantic v2 and FastAPI contract patterns relevant to create/read/update
  chapter schemas
- how the existing `VersionedMixin` fits chapter contracts
- validation boundaries for chapter fields named in the prompt and current
  scope docs
- partial-update behavior for PATCH-style request bodies
- which parts of the `java-interview-setup` optimistic-locking and audit
  patterns carry over to API contracts
- Discord snowflake handling at the Python API boundary

It does not propose an implementation or write the target contract module.

## Local baseline

- The API package already states that contracts are the public API
  boundary and that optimistic-locking-capable contracts use
  `VersionedMixin`
  ([contracts `__init__`](/home/nes/discord/services/api/app/contracts/__init__.py:1)).
- The current base contract mixin is a required `version: int` with
  `ge=0`, and its docstring already says it is for read/update contracts
  and excluded from create contracts
  ([base.py](/home/nes/discord/services/api/app/contracts/base.py:1)).
- The repo currently resolves `pydantic 2.13.0` and `fastapi 0.135.3`
  in `services/api`, with `pydantic>=2.9.0` and `fastapi>=0.115.0`
  declared in the package metadata
  ([pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)).
- The current proposal treats chapters as durable current-state records
  and distinguishes them from per-chapter roles/channels/members
  ([proposal](/home/nes/discord/proposals/01-v1-scope.md:109)).
- D4 makes chapter intake, chapter history retention, and future
  chapter-scoped rules first-class, which means chapter records are not
  transient provisioning-only objects
  ([DECISIONS.md](/home/nes/discord/DECISIONS.md:79)).
- `services/api/app/contracts/chapters.py` does not exist yet in the
  current tree.

## Primary sources

- Local repo:
  - [services/api/app/contracts/base.py](/home/nes/discord/services/api/app/contracts/base.py:1)
  - [services/api/app/contracts/__init__.py](/home/nes/discord/services/api/app/contracts/__init__.py:1)
  - [services/api/app/core/settings.py](/home/nes/discord/services/api/app/core/settings.py:1)
  - [DECISIONS.md](/home/nes/discord/DECISIONS.md:79)
  - [proposals/01-v1-scope.md](/home/nes/discord/proposals/01-v1-scope.md:109)
  - [research/22-contracts-base.md](/home/nes/discord/research/22-contracts-base.md:1)
  - [research/23-discord-settings.md](/home/nes/discord/research/23-discord-settings.md:176)
- Java reference:
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java:1)
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java:1)
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java:1)
  - [.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:1)
  - [.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java:1)
- Official docs:
  - Pydantic models: https://docs.pydantic.dev/latest/concepts/models/
  - Pydantic fields: https://docs.pydantic.dev/latest/concepts/fields/
  - Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/
  - Pydantic types / `StringConstraints`: https://docs.pydantic.dev/latest/api/types/
  - Pydantic migration guide: https://docs.pydantic.dev/latest/migration/
  - FastAPI body updates / partial updates: https://fastapi.tiangolo.com/tutorial/body-updates/
  - FastAPI separate input/output schemas: https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/
  - Discord developer reference / snowflakes: https://docs.discord.com/developers/docs/reference#snowflakes

## 1. Pydantic v2 CRUD contract patterns

### Separate create/read/update contracts are the normal shape

Across FastAPI and Pydantic v2, the CRUD pressure points are materially
different enough that separate models are the stable pattern:

- create contracts carry only client-supplied mutable inputs
- read contracts carry server-assigned and persisted state
- update contracts carry concurrency state plus mutable inputs
- PATCH contracts differ again because omission and explicit `null` have
  different meanings

That split is sharper in Pydantic v2 because `Optional[T]` no longer
means “not required” by itself. A field only becomes non-required when
it has a default. The result is that one shared chapter model would have
to serve incompatible purposes:

- create does not want server-assigned fields such as `id`,
  `created_at`, or `version`
- read does want them, and wants them required
- PATCH wants most mutable fields optional-by-default, but still needs
  to surface whether a field was omitted or sent

In practice this means a single model pushes too many semantics into one
schema and makes generated OpenAPI less precise.

### FastAPI encourages separate request/response shapes

FastAPI’s documented “separate input/output schemas” guidance matches
that split. The framework generates clearer OpenAPI when request and
response bodies reflect what each side actually sends instead of one
overloaded model.

For chapters specifically, the pressure to separate models is higher
than average because the prompt’s field set already mixes:

- client-entered fields: `name`, `slug`
- Discord resource identifiers that may be absent until provisioning:
  `discord_category_id`, `discord_officer_role_id`,
  `discord_member_role_id`
- server-assigned fields: `id`, `created_at`, `version`
- lifecycle state: `status`

### Full-update and partial-update are distinct contract shapes

FastAPI’s partial update guidance is PATCH-specific. A full replacement
style update and a partial update are not the same shape in Pydantic:

- full update can keep fields required
- PATCH usually makes mutable fields optional with defaults so omission
  is legal

That distinction matters for chapters because chapter updates are likely
to be patch-like: status changes, renames, late population of Discord
IDs during provisioning, and archival.

## 2. `VersionedMixin` integration strategy

### What the current repo already establishes

The current local baseline is explicit:

- `VersionedMixin` is a required `version: int = Field(ge=0)`
- its docstring says it belongs on read/update contracts, not create
  contracts
  ([base.py](/home/nes/discord/services/api/app/contracts/base.py:4))

That is consistent with the earlier local `VersionedMixin` research and
with the project-wide optimistic-locking test rule:

- read returns version `N`
- update submits version `N`
- successful update returns version `N+1`
- stale update returns `409 Conflict`

### Which chapter contracts need version

Research-wise, the split is:

- create contract: does not need `version`
- read contract: does need `version`
- update/PATCH contract: does need `version`

The rationale comes from the Java reference. `VersionedDto` exposes
`version()` as part of the DTO boundary, and `EntityValidator` checks
submitted DTO version against current entity version before mutation
([VersionedDto.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java:1),
[EntityValidator.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java:1)).

The important boundary here is that Pydantic validates presence and
basic numeric constraints, but stale-write detection is not a Pydantic
concern. The stale check remains service/domain logic, mirroring the
Java reference.

### PATCH introduces one nuance

PATCH models usually make fields optional by assigning defaults, but the
optimistic-lock version is different: it is concurrency state, not a
partial field. So the research tension is:

- mutable chapter fields trend toward “optional with default”
- `version` trends toward “required integer”

That tension is why version typically remains explicit instead of being
folded into the same optional pattern as the mutable fields.

## 3. Validation rules by field

## `slug`

The requested slug rule is stricter than plain “string with min/max
length”. The design space here is a constrained lowercase ASCII slug:

- lowercase letters and digits only
- internal hyphens allowed
- no spaces
- no leading or trailing hyphen
- no empty path segments if split on `-`

The common regex shape for that rule family is:

```text
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

Pydantic v2 supports this cleanly through field constraints or
`StringConstraints(pattern=...)`. Pattern-level validation is stronger
than post-hoc normalization because it prevents inputs that would need
rewriting.

Length also needs an explicit bound. The prompt does not fix one, so
the open research fact is not “whether to bound it” but “where the
project wants the bound.” Slug length should be contract-bounded rather
than left only to the database.

## `name`

The prompt defines `name` as non-empty and bounded. Two validation
details matter:

- `min_length=1` alone allows whitespace-only strings
- if whitespace-only names are invalid, either trimming or a validator
  is needed in addition to length bounds

So “non-empty” is not one question but two:

- raw length must be at least 1
- normalized content must not collapse to empty after trimming

As with slug, the exact max length is not specified in the prompt or
proposal, but the bound belongs at the contract layer as well as the DB
layer.

## Discord snowflake IDs

For `discord_category_id`, `discord_officer_role_id`, and
`discord_member_role_id`, the prompt’s “positive integers” rule matches
the repo’s current Python treatment of Discord IDs:

- settings already type guild IDs as `int`
  ([settings.py](/home/nes/discord/services/api/app/core/settings.py:5))
- prior local research already established that current repo convention
  is Python `int` even though Discord’s HTTP docs describe snowflakes as
  string-serialized IDs
  ([research/23-discord-settings.md](/home/nes/discord/research/23-discord-settings.md:176))

Important design-space fact: this is safe for Python itself, but it is
not neutral across all clients. Discord documents string serialization
to avoid overflow/precision problems in languages and environments that
do not safely represent all 64-bit integers as JSON numbers. That
matters here because Humility’s architecture also plans a web client and
generated shared TypeScript contracts.

So there are two valid observations at once:

- within Python/FastAPI/Pydantic, positive integer validation fits the
  repo’s current convention
- at the JSON contract boundary, snowflake-as-number introduces a
  precision risk for JavaScript clients once IDs exceed `2^53 - 1`

For validation specifically, the field-level rule is at least:

- numeric identifier
- greater than zero

Strictness is a separate dimension. By default Pydantic may coerce some
inputs; strict typing is only needed if the API contract wants to reject
stringified numerals at validation time instead of coercing them.

## `status`

The prompt fixes status to a closed set: `active`, `archived`,
`provisioning`. That maps naturally to an enum-valued contract field.

At the research level, the key value of an enum here is not only runtime
validation but schema clarity:

- generated OpenAPI can expose the closed set directly
- clients can distinguish lifecycle states from arbitrary strings
- invalid future status strings fail at the boundary instead of leaking
  into downstream logic

## Server-assigned fields mentioned in context

The prompt’s chapter table fields also include `id` and `created_at`.
These are not client-entered fields in the normal CRUD split. In
Pydantic/FastAPI contract terms they are read-side data, not create-side
requirements, and not usually mutable update inputs.

## 4. Partial update patterns

### Pydantic v2 required/optional behavior is explicit

In Pydantic v2, `field: T | None` is still required unless a default is
provided. For PATCH-style contracts, optionality therefore requires
explicit defaults such as `= None`.

Local runtime probes in this repo confirmed the important behavior:

- a field declared as `name: str | None = None` is not required in the
  generated schema
- `model_dump(exclude_unset=True)` includes only fields the client
  actually sent
- `model_fields_set` preserves the omitted-vs-sent distinction

For example, a local probe with a PATCH-like model instantiated as
`ChapterPatch(name="Alpha")` produced:

- `model_fields_set == {"name"}`
- `model_dump(exclude_unset=True) == {"name": "Alpha"}`

### Omitted and explicit `null` are different states

This is the main PATCH subtlety for chapter contracts.

If a PATCH field is declared with a default of `None`, there are three
possible states at the API boundary:

- omitted entirely
- sent with a concrete value
- sent explicitly as `null`

Pydantic can preserve that distinction through `model_fields_set`, even
when the in-memory attribute value is `None`.

That matters if any chapter field is nullable in storage or workflow.
Discord IDs are the clearest example: if they begin unset during
provisioning, an API may later need to distinguish “leave untouched”
from “clear this value” from “set this value.”

### PATCH semantics belong at the boundary; conflict semantics do not

FastAPI/Pydantic handle the shape of a partial body. They do not decide
whether a particular patch is stale, legal in the current state, or
allowed for a chapter in `archived` status. Those are downstream
service-layer concerns.

## 5. Applicability of `java-interview-setup` patterns

### Optimistic locking maps directly

The Java reference is directly relevant in one area: chapter DTOs that
represent mutable state should expose version as contract data, and
service logic should reject stale writes by comparing submitted version
to persisted version before applying changes
([EntityValidator.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java:1)).

The controller tests in the reference confirm the expected externally
visible behavior:

- reads return versioned DTOs
- successful updates increment version
- stale updates return `409 Conflict`
  ([TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:44),
  [TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:136)).

### Audit info informs storage and read models more than write models

`AbstractEntity` embeds `AuditInfo`, and the audit tests show creation
and modification metadata being populated from request context
([AbstractEntity.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java:1),
[TestAuditInfo.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java:1)).

That pattern is relevant to chapters as a domain concern because
chapters are long-lived administrative records, but it does not imply
that create/update contracts should accept audit fields from clients.
The reference uses audit metadata as entity-managed information, not as
client-controlled input.

At the API-contract layer, the main applicability is:

- optimistic-lock version belongs in mutable DTOs
- audit actor/timestamps are usually server-managed metadata
- if exposed at all, audit fields are read-side data, not create/update
  input fields

### Domain validation and contract validation stay separate

The Java reference also reinforces that not every invariant belongs in
the DTO validator. DTO/contracts carry structural and simple field
validation. Staleness, existence, cross-record checks, and state-machine
rules happen after the contract boundary.

For chapters, that means field validation such as slug pattern or
positive snowflake IDs belongs in the Pydantic contract, while rules
such as “cannot archive while provisioning run is active” do not.

## 6. Discord snowflake handling

The chapter contract design has a real cross-surface type tension:

- Python can safely hold Discord snowflakes as arbitrary-size integers
- Discord’s own docs describe snowflakes as string-serialized at the
  HTTP layer
- Humility plans both Python daemon consumers and a TypeScript/web
  surface

The current repo convention is integer-based on the Python side, but
the design space is not purely a Python question because the contract
module sits at an API boundary. The important research fact is not that
one choice is already settled everywhere; it is that Python-int and
JSON-number are not equivalent once browser/TypeScript consumers enter
the picture.

## Findings summary

- Pydantic v2 and FastAPI strongly favor separate create/read/update
  chapter models because required fields, server-assigned fields, and
  PATCH optionality are materially different schema shapes.
- The existing `VersionedMixin` aligns with the documented optimistic
  locking contract: create omits version; read and update include it.
- Chapter field validation divides cleanly into:
  - slug: constrained lowercase hyphenated identifier
  - name: bounded non-empty normalized text
  - Discord IDs: positive snowflake identifiers with a Python-int vs
    JSON-client precision tension
  - status: closed enum of `active`, `archived`, `provisioning`
- PATCH contracts need explicit defaults for optional fields in
  Pydantic v2, and omitted-vs-explicit-null semantics matter.
- The Java reference is highly relevant for optimistic locking and only
  partially relevant for audit info; audit metadata is server-managed,
  not client-supplied contract input.
