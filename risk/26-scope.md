# Scope Risk Assessment: Chapter CRUD Contracts (`services/api/app/contracts/chapters.py`)

## Overall: LOW

The proposal defines a focused Pydantic contract module with exactly
four public symbols — `ChapterStatus`, `ChapterCreate`, `ChapterRead`,
`ChapterUpdate` — covering only the API boundary shape for chapter CRUD.
Every field traces to a documented need in the research or synthesis.
Validation rules are limited to structural constraints (lengths, regex,
positivity) and explicitly exclude business rules. The anti-scope
section fences out ten categories of expansion. The module owns schema
shape only and does not reach into service, repository, or persistence
concerns.

## Findings

### Finding 1: Appropriately sized for a contracts module
- Severity: LOW
- Description: The proposal delivers exactly what a CRUD contract module
  should own: one lifecycle enum, one create schema, one read schema,
  and one update schema. The field set is drawn directly from the chapter
  table definition in the v1 scope proposal and the research synthesis.
  `ChapterCreate` carries two fields (name, slug). `ChapterRead` carries
  nine fields (id, name, slug, status, three Discord IDs, created_at,
  version). `ChapterUpdate` carries six mutable fields plus version. The
  module introduces no utility functions, no service helpers, no factory
  methods, and no internal-only types. This is proportionate to a single
  entity's API contract surface.

### Finding 2: No service or repository logic detected
- Severity: LOW
- Description: The proposal explicitly states that services and
  repositories remain responsible for stale-write detection, uniqueness
  checks, state-machine rules, and persistence (proposal lines 33-34).
  The "What this module should not validate" section (proposal lines
  188-197) enumerates six specific business checks that are excluded:
  slug uniqueness, name uniqueness, Discord snowflake existence, status
  transition validity, archived-chapter edit guards, and provisioning
  completion checks. The contract validates presence and shape; the
  service layer validates meaning. The boundary between schema validation
  and domain validation matches the Java reference pattern where
  `EntityValidator` performs stale-write checks outside the DTO
  (research lines 158-167).

### Finding 3: Validation rules are proportionate
- Severity: LOW
- Description: Each validation rule maps directly to a structural
  constraint, not a business rule:
  - `name`: trim whitespace, min length 1, max length 100 — prevents
    empty/whitespace-only names and bounds storage. The trim-then-check
    pattern is standard for user-facing text fields.
  - `slug`: regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`, max length 50 —
    enforces URL-safe slug format at the boundary rather than
    normalizing. Research confirms pattern validation is stronger than
    post-hoc normalization (research lines 184-208).
  - Discord IDs: `int | None`, `> 0` when present — matches existing
    repo convention for snowflake handling (settings already types guild
    IDs as int). The nullable design correctly models provisioning state
    where Discord resources may not yet exist.
  - `version`: inherited from `VersionedMixin`, `ge=0` — reuses the
    existing base contract rather than redefining version semantics.
  - `status`: closed `StrEnum` with three values — prevents arbitrary
    strings without imposing transition rules.
  No validator performs cross-field checks, database lookups, or
  state-machine enforcement. The rules are proportionate to an API
  boundary contract.

### Finding 4: No coupling to unbuilt subsystems
- Severity: LOW
- Description: The module's only internal dependency is `VersionedMixin`
  from the existing `base.py`, which is already implemented and tested.
  The proposal does not reference or depend on: chapter services (not
  yet built), chapter repositories (not yet built), Discord provisioning
  workflows (not yet built), form contracts (future work), or membership
  contracts (future work). Discord snowflake fields are typed as
  `int | None` rather than referencing any Discord client library type
  or provisioning module. The `ChapterStatus` enum defines lifecycle
  vocabulary without importing or coupling to any state-machine
  implementation. The proposal explicitly acknowledges the snowflake
  precision concern for JavaScript clients (proposal lines 230-235)
  and defers it to the serialization layer rather than pulling in a
  shared-types dependency now.

### Finding 5: Anti-scope is clear and sufficient
- Severity: LOW
- Description: The anti-scope section (proposal lines 239-252)
  enumerates ten explicit exclusions: service methods, repository types,
  database/Alembic definitions, optimistic-lock conflict handling, audit
  metadata, list/search/filter/pagination models, nested form/roster/
  activity-rule/Discord detail collections, Discord provisioning
  workflows, and package-wide re-export strategy. Each exclusion maps to
  a known expansion path that would pull the module beyond contract
  scope. The exclusion of audit metadata is well-targeted — the research
  confirms audit fields are server-managed, not client-supplied, per the
  Java reference pattern (research lines 355-369). The exclusion of
  list/pagination models correctly defers collection-level response
  shapes to a later proposal rather than over-building this one. The
  exclusion of nested collections prevents the chapter contract from
  becoming a god-object that embeds forms, rosters, and Discord
  resources.

### Finding 6: Fits cleanly with later form/ticket contracts
- Severity: LOW
- Description: The proposal's composability section (proposal lines
  40-43) explicitly states that later form, membership, or chapter-
  settings contracts should reference chapter schemas or the chapter ID
  rather than replace or embed into this module. The synthesis confirms
  this design intent: form contracts will reference chapters by ID, not
  embed forms in chapter contracts (synthesis lines 52-54). The module
  exports clean, self-contained schemas with no forward references to
  unbuilt contract types. `ChapterRead` exposes `id: int` which is the
  natural foreign key for composition. The `ChapterStatus` enum is a
  standalone vocabulary type that form or ticket contracts can import
  for filtering or display without pulling in the full chapter schema.
  This composability approach matches the existing contract package
  architecture where `base.py` provides shared mixins and per-entity
  modules provide entity-specific schemas.

## Recommendations

None. The proposal is well-scoped for a single-entity contract module.
No changes required.
