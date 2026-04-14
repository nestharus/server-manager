# Proposal: `services/api/app/contracts/base.py`

Date: 2026-04-13

## Goal

Define `services/api/app/contracts/base.py` as the API contract layer's
minimal shared base for optimistic-locking-aware schemas.

The module should provide one public class, `VersionedMixin`, that
encodes the version field as part of the external API contract for
entities that support optimistic locking. Its job is to make version
visible, required, and schema-stable for read and update contracts.

This proposal is design only. It does not include implementation code.

## Design

The module should export one public model:

```python
class VersionedMixin(BaseModel):
    version: int = Field(ge=0)
```

### Field definition

- `version: int = Field(ge=0)`
  Required optimistic-locking version field.
- No default value.
- No nullable type.
- No aliasing.
- No custom validator.
- No `model_config`.

That shape is intentional. In Pydantic v2, a required `int` field with
`Field(ge=0)` yields the clean OpenAPI surface Humility needs:

- `version` is listed as required
- schema type is `integer`
- lower bound is emitted as `minimum: 0`
- the field does not become optional or nullable in request schemas

### Intended usage

`VersionedMixin` should be used by contracts where the client must
observe or submit the current version:

- read/response schemas
- update/request schemas

It should not be used by create/request schemas. Create contracts should
be separate models that omit `version`, and the server should assign
initial version `0` when the entity is created.

That gives the public contract split Humility needs:

- create input: no `version`
- read output: required `version`
- update input: required `version`
- update output: required `version`

### Module surface

The module should stay intentionally small:

- public export: `VersionedMixin`
- private responsibility: define the shared version field
- no helper functions
- no alternate base classes
- no schema examples or OpenAPI decoration beyond the field constraint

## Architecture

This module belongs in the contracts layer because version is a public
API concern, not an internal repository detail.

The intended class hierarchy is:

```python
BaseModel
  -> VersionedMixin
    -> SubmissionRead
    -> SubmissionUpdate
    -> TicketRead
    -> TicketUpdate
    -> ChapterRead
    -> ChapterUpdate
```

Create models remain a separate branch:

```python
BaseModel
  -> SubmissionCreate
  -> TicketCreate
  -> ChapterCreate
```

This separation matters more than trying to force one model shape across
all CRUD operations. The optimistic-locking contract is different for
creation than it is for reads and updates, and the OpenAPI surface
should reflect that explicitly.

### Why version starts at 0 without a default here

The system requirement is that newly created entities begin at version
`0`. This module should not encode that by making `version` default to
`0`, because doing so would make the field non-required in input schemas
and blur the distinction between create and update contracts.

Instead:

- create models omit `version`
- creation logic assigns `version = 0`
- read/update models include `VersionedMixin`

That preserves both semantics:

- initial persisted version is `0`
- update callers must still send the current version explicitly

### Multi-base guidance

`VersionedMixin` should not declare `model_config`. That keeps the mixin
safe to compose in the common case and avoids introducing config-merging
ambiguity into every contract that inherits it.

If a concrete contract later needs model-level Pydantic config, that
config should be defined on the final concrete class, not on
`VersionedMixin`.

## Tradeoffs

- `BaseModel` parent vs plain Python mixin
  Using `BaseModel` is the documented, stable Pydantic v2 inheritance
  pattern. It guarantees field collection, validation behavior, and JSON
  Schema generation on supported ground. A plain annotated mixin may
  work in local probes, but that behavior is not the primary documented
  composition surface and is a weaker foundation for a public contract
  module.
- Required field vs `version=0` default
  A default would make creation look simpler, but it would also make the
  field optional in request schemas and weaken the update contract.
  Keeping the field required forces the correct concurrency behavior for
  read/update flows, at the cost of needing separate create models.
- No `model_config` vs shared config in the mixin
  Adding config here would create hidden coupling for every future
  contract subclass and would reintroduce the multiple-base config caveat
  the research surfaced. Omitting config keeps the mixin narrowly
  focused, but means any broader contract policy must live elsewhere.
- Field-only mixin vs richer concurrency abstraction
  This module could try to carry helpers, examples, or conflict-related
  metadata, but that would mix transport concerns with workflow and
  persistence semantics. A single constrained field is enough for the
  contract layer and keeps the module reusable across entities.

## Anti-scope

This module should explicitly not do the following:

- Implement optimistic-lock checks
  Version comparison and stale-write detection belong in service/domain
  validation, not in the Pydantic contract model itself.
- Map stale writes to HTTP `409 Conflict`
  Error translation belongs in endpoint/service behavior, not in
  `contracts/base.py`.
- Assign initial versions during creation
  The module defines the public field shape; create-time assignment of
  `0` belongs in create workflow logic.
- Define create schemas
  `VersionedMixin` exists for version-carrying contracts. Create models
  should be separate concrete schemas.
- Carry unrelated base fields
  No `id`, timestamps, audit fields, actor metadata, status, or other
  shared contract concerns should be added here.
- Introduce compatibility shims
  No nullable `version`, no deprecated aliases, and no dual support for
  both omitted and required version semantics.

## Test Contract

Tests for this proposal should be split into two levels: module-level
contract tests for `VersionedMixin` itself, and downstream entity/API
tests for full optimistic-locking behavior.

### Module-level tests

Tests for `services/api/app/contracts/base.py` should verify:

- `VersionedMixin(version=0)` is valid.
- Positive integers are accepted.
- Negative integers are rejected.
- Omitting `version` raises validation failure.
- `model_json_schema()` marks `version` as required.
- `model_json_schema()` emits `type: integer`.
- `model_json_schema()` emits `minimum: 0`.
- `model_json_schema()` does not emit `default`.
- `model_json_schema()` does not emit a nullable union such as
  `anyOf: [integer, null]`.

### Inheritance tests

A concrete subclass test should verify that a model inheriting from
`VersionedMixin` still exposes the same required `version` field in both
validation and generated schema.

### Downstream optimistic-locking tests

Feature-level tests for versioned entities should verify the full
contract described in `AGENTS.md` and the Java reference:

- reading a newly created entity returns `version == 0`
- updating with the current version succeeds
- a successful update returns the incremented version
- updating with a stale version returns `409 Conflict`

Those behaviors are required by the overall system, but they are not
implemented inside `VersionedMixin` and therefore should not be treated
as unit tests for this module alone.
