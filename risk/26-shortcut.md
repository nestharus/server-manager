# Shortcut risk assessment — proposals/26-chapters-contract.md

Date: 2026-04-13
Assessor: claude-opus (shortcut)

## Verdict

**LOW**

The proposal makes fully resolved design decisions for all four contract
symbols and their validation rules. `VersionedMixin` is reused, not
redefined. Field constraints are appropriate schema-level literals, not
hardcoded values masking configurable parameters. The snowflake-as-integer
convention is an acknowledged repo-wide pattern with an explicit
cross-boundary risk callout deferred to the correct layer. No
compatibility shims, duplicated logic, or unresolved TODOs were found.

## Findings

### Finding 1 — No compatibility shims or backward-compat patterns

- **Severity**: LOW
- **Criterion**: 1 (compatibility shims)
- **Description**: `services/api/app/contracts/chapters.py` does not
  exist yet. There are no prior chapter contracts to be
  backward-compatible with. The proposal creates four new symbols from
  scratch. No feature flags, dual-write paths, re-export shims, or
  `_deprecated` aliases are introduced. The anti-scope section
  explicitly excludes "package-wide re-export strategy outside the
  chapter module itself."
- **Recommendation**: Accept. Clean greenfield contract.

### Finding 2 — Field constraint literals are appropriate, not hardcoded shortcuts

- **Severity**: LOW
- **Criterion**: 2 (hardcoded values that should be configurable)
- **Description**: The proposal fixes `name` max length at `100`, `slug`
  max length at `50`, slug regex at `^[a-z0-9]+(?:-[a-z0-9]+)*$`, and
  `ChapterStatus` to exactly three values. These are schema-boundary
  constants: they define the shape of the API surface and must match
  the database column constraints. Making max lengths or regex patterns
  runtime-configurable would decouple the contract from the storage
  layer and produce unstable OpenAPI schemas. The status enum is a
  closed lifecycle vocabulary by design — new states require a
  deliberate schema migration, not a config change.
- **Recommendation**: Accept. Contract-level literals are the correct
  pattern for API boundary shapes.

### Finding 3 — No duplicated logic from existing code

- **Severity**: LOW
- **Criterion**: 3 (duplicated logic)
- **Description**: The proposal explicitly inherits `VersionedMixin`
  from `base.py` for `ChapterRead` and `ChapterUpdate` rather than
  redefining `version: int = Field(ge=0)` in each model. No other
  contract modules exist in the tree to duplicate from. The validation
  rules for `name`, `slug`, and snowflake IDs are defined here for the
  first time. The proposal notes that "shared string rules" should be
  consistent across create/read/update models, which is
  intra-module consistency, not cross-module duplication.
- **Recommendation**: Accept. `VersionedMixin` reuse is correct.

### Finding 4 — Snowflake-as-integer deferral is at the correct boundary

- **Severity**: LOW
- **Criterion**: 4 (deferred TODOs) and 5 (unvalidated Discord type assumptions)
- **Description**: The proposal types Discord snowflakes as `int | None`
  with `> 0` when present. It explicitly acknowledges the JS precision
  risk: "This carries a known precision risk for JavaScript clients once
  values exceed `2^53 - 1`." It then says the fix belongs at the
  "API/shared-types boundary later rather than by widening this contract
  module now." The research validates that Python `int` is the current
  repo convention (settings already type guild IDs as `int`) and that
  the cross-boundary tension is real but belongs to the shared TypeScript
  types layer, not to individual Python contract modules.
- **Why this is not a shortcut**: The proposal does not pretend the
  tension does not exist. It names the risk, confirms it matches an
  established convention, and identifies the correct future resolution
  layer. A shortcut would silently use `int` without acknowledging the
  downstream impact. A premature fix would widen this single contract
  module to solve a repo-wide serialization concern.
- **Recommendation**: Accept. Honest deferral to the correct layer.

### Finding 5 — Discord type assumptions are validated

- **Severity**: LOW
- **Criterion**: 5 (unvalidated assumptions about Discord types)
- **Description**: The proposal assumes three Discord snowflake fields:
  `discord_category_id`, `discord_officer_role_id`, and
  `discord_member_role_id`. Each is nullable to handle provisioning
  state where Discord resources do not yet exist. The `> 0` constraint
  matches Discord's snowflake definition (unsigned 64-bit integers,
  always positive when valid). The research cross-references the Discord
  developer docs on snowflakes, the existing `settings.py` guild ID
  typing, and prior local research (`research/23-discord-settings.md`).
  No assumptions are made about Discord object structures beyond the
  snowflake ID type.
- **Recommendation**: Accept. Assumptions are validated against docs and
  existing repo convention.

### Finding 6 — VersionedMixin integration is clean

- **Severity**: LOW
- **Criterion**: 6 (shortcuts in VersionedMixin integration)
- **Description**: The proposal's integration matches `base.py`
  exactly. `VersionedMixin` declares `version: int = Field(ge=0)` and
  its docstring says "for read/update contracts. Exclude from create
  contracts." The proposal applies this rule without modification:
  `ChapterRead(VersionedMixin)` and `ChapterUpdate(VersionedMixin)`
  inherit version; `ChapterCreate(BaseModel)` does not. Stale-write
  detection is explicitly delegated to the service layer with `409
  Conflict` mapping. The contract validates only "presence and basic
  numeric bounds." No version field is redefined, overridden, or given
  a default that would weaken the required constraint.
- **Recommendation**: Accept. Exact alignment with existing mixin
  contract.

## Overall assessment

All six criteria were evaluated against the proposal text, research
document, existing `base.py` mixin, `__init__.py` package contract, and
project decision log. No shortcut pattern was found at MEDIUM or HIGH
severity. The proposal creates four narrowly scoped contract symbols with
fully resolved field definitions, proper mixin reuse, and honest
treatment of the one cross-boundary tension (snowflake serialization).
The anti-scope section draws clean lines that prevent scope creep without
hiding deferred shortcuts. Every design decision in this module is
either resolved in the proposal or explicitly identified as belonging
to a different layer.
