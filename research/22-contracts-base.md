# Research: Base Contract Module (`VersionedMixin`)

Date: 2026-04-13

## Scope

This note documents the current problem space for a base contract module
at `services/api/app/contracts/base.py` that would provide a
`VersionedMixin` for Pydantic schemas supporting optimistic locking.

It is limited to:

- what the current repo already says about optimistic locking and API
  contracts
- what the `java-interview-setup` reference encodes about version
  semantics
- what Pydantic v2, FastAPI, and the installed local runtime expose for
  model inheritance, validation, and OpenAPI schema generation
- which Humility entities appear likely to carry versioned API contracts
  based on the current design docs and research

It does not propose a final module design or implementation.

## Local Baseline

- The API package already declares that contracts are the public API
  boundary and that they are expected to use `VersionedMixin` for
  optimistic locking-capable entities, but the `base.py` module does not
  exist yet
  ([services/api/app/contracts/__init__.py](/home/nes/discord/services/api/app/contracts/__init__.py:1)).
- The API service is on FastAPI and Pydantic v2, with `pydantic>=2.9.0`
  declared in the service package and `pydantic 2.13.0` currently
  resolved in the local `services/api` runtime
  ([services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)).
- The current live API surface is still minimal; the only implemented
  endpoint today is `/api/v1/health`
  ([services/api/app/api/v1/endpoints/health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1)).
- Project guidance treats optimistic locking as a contract-level concern,
  not an internal-only persistence detail: tests for versioned entities
  must verify `read -> version N`, `update with N -> N+1`, and `stale
  update with N -> 409 Conflict`
  ([AGENTS.md](/home/nes/discord/AGENTS.md:144)).

## Primary Sources

- Local repo files:
  - [AGENTS.md](/home/nes/discord/AGENTS.md:144)
  - [services/api/app/contracts/__init__.py](/home/nes/discord/services/api/app/contracts/__init__.py:1)
  - [services/api/pyproject.toml](/home/nes/discord/services/api/pyproject.toml:1)
  - [services/api/app/api/v1/endpoints/health.py](/home/nes/discord/services/api/app/api/v1/endpoints/health.py:1)
  - [docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41)
  - [research/02-humility-needs.md](/home/nes/discord/research/02-humility-needs.md:45)
- Java reference files:
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java:1)
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java:1)
  - [.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java:1)
  - [.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:1)
  - [.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java:1)
- Official docs:
  - Pydantic configuration:
    https://docs.pydantic.dev/latest/concepts/config/
  - Pydantic fields:
    https://docs.pydantic.dev/latest/concepts/fields/
  - Pydantic models:
    https://docs.pydantic.dev/latest/concepts/models/
  - Pydantic validators:
    https://docs.pydantic.dev/latest/concepts/validators/
  - Pydantic JSON Schema:
    https://docs.pydantic.dev/latest/concepts/json_schema/
  - Pydantic migration guide:
    https://docs.pydantic.dev/latest/migration/
  - Why use Pydantic:
    https://docs.pydantic.dev/latest/why/
  - FastAPI separate input/output schemas:
    https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/
  - FastAPI request examples / `json_schema_extra`:
    https://fastapi.tiangolo.com/tutorial/schema-extra-example/
- Local runtime observations:
  - `cd services/api && uv run python` with `pydantic 2.13.0`
  - targeted `BaseModel` inheritance and `model_json_schema()` probes

## 1. Optimistic Locking in Pydantic: shape of the version field

### What the Java reference says

- The reference entity base uses a primitive `long version` with JPA
  `@Version`
  ([AbstractEntity.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/entity/AbstractEntity.java:1)).
- The DTO interface also exposes `long version()`, so version is part of
  the external DTO contract, not just persistence state
  ([VersionedDto.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/dto/VersionedDto.java:1)).
- Staleness checks compare the submitted DTO version to the current
  entity version and raise an optimistic-locking failure when they do
  not match
  ([EntityValidator.java](/home/nes/discord/.refs/java-interview-setup/src/main/java/com/real/interview/common/validator/EntityValidator.java:22)).
- Controller tests show the reference semantics clearly:
  - reads return `version: 0` for a newly created entity
  - updates submit the current version and receive `version: 1`
  - stale updates return `409 Conflict`
  ([TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:44),
  [TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:136),
  [TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:307)).

### What Pydantic v2 documents

- Pydantic v2 no longer gives `Optional[...]` an implicit default of
  `None`; a field is only non-required when an explicit default is
  present
  ([Pydantic migration guide](https://docs.pydantic.dev/latest/migration/)).
- Required fields are represented by annotation-only fields or by
  explicit required `Field(...)`
  ([Pydantic models docs, required fields](https://docs.pydantic.dev/latest/concepts/models/)).
- `Field()` constraints contribute to JSON Schema. For integers this
  includes lower-bound metadata such as `gt` / `ge`
  ([Pydantic fields docs](https://docs.pydantic.dev/latest/concepts/fields/)).

### Local runtime observations (`pydantic 2.13.0`)

- `version: int` is required.
- `version: int | None` is still required.
- `version: int | None = None` is not required and generates a schema
  with `anyOf: [integer, null]` plus `default: null`.
- `version: int = Field(ge=0)` generates JSON Schema with
  `type: integer`, `minimum: 0`, and `required: ["version"]`.
- `version: int | None = Field(default=None, ge=0)` generates JSON
  Schema without a `required` list for that field.

Example runtime results from this repo:

```python
from pydantic import BaseModel, Field

class RequiredVersion(BaseModel):
    version: int = Field(ge=0)

class NullableVersion(BaseModel):
    version: int | None = Field(default=None, ge=0)
```

`RequiredVersion.model_json_schema()` reported `required: ['version']`.
`NullableVersion.model_json_schema()` reported no `required` entry and
used `anyOf` with `integer` and `null`.

### Problem-space consequence

The core version-field tension is between two independently documented
facts:

- the project and Java reference both treat version as contract-level
  concurrency state
- in Pydantic/FastAPI, “required integer” and “nullable defaulted
  integer” produce materially different request schemas, validation
  behavior, and OpenAPI output

That difference matters even before any implementation choice is made.

## 2. Mixin Pattern in Pydantic v2: inheritance and composition surface

### What Pydantic documents clearly

- Pydantic’s primary supported model pattern is classes that inherit
  from `BaseModel`
  ([Pydantic models docs](https://docs.pydantic.dev/latest/concepts/models/)).
- Configuration is documented on `BaseModel` classes via
  `model_config = ConfigDict(...)` or class arguments
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).
- Pydantic explicitly documents “create your own custom parent class”
  as the way to define inherited model configuration, and says subclass
  config is merged with parent config
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).
- Pydantic models can also be combined with Python abstract base classes
  (`BaseModel, abc.ABC`)
  ([Pydantic models docs](https://docs.pydantic.dev/latest/concepts/models/)).
- Validators defined on base classes can target subclass fields by using
  `check_fields=False`; the docs call this out as specifically useful
  for base-class validators
  ([Pydantic validators docs](https://docs.pydantic.dev/latest/concepts/validators/)).

### What Pydantic also warns about

- If a model inherits from multiple bases, Pydantic currently does not
  follow Python MRO for config resolution
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).
- Pydantic models are configuration boundaries. Config does not
  implicitly propagate through nested model fields
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).

### Local runtime observations (`pydantic 2.13.0`)

- Multiple `BaseModel` bases do merge fields and config, but the order of
  bases changes the resulting field order and the winning config values.
- In local probes, a plain non-`BaseModel` annotated class also
  contributed fields when mixed into a model, but this behavior was an
  observation from the installed runtime, not something described in the
  Pydantic concept pages reviewed here.

Example runtime probe:

```python
from pydantic import BaseModel, ConfigDict

class ExtraAllow(BaseModel):
    model_config = ConfigDict(extra='allow')
    a: int | None = None

class ExtraForbid(BaseModel):
    model_config = ConfigDict(extra='forbid')
    b: int | None = None

class CombinedLeft(ExtraAllow, ExtraForbid):
    x: int

class CombinedRight(ExtraForbid, ExtraAllow):
    x: int
```

In this repo’s local runtime:

- `CombinedLeft.model_config` resolved `extra='forbid'`
- `CombinedRight.model_config` resolved `extra='allow'`
- field order also changed with base ordering

### Problem-space consequence

The inheritance question is not just “can a mixin add a field?” The
documented problem space includes:

- the supported inheritance surface for config and validators lives on
  `BaseModel` parents
- multiple-base inheritance has a documented config caveat
- local runtime behavior is broader than the explicitly documented
  surface

That means “works in a probe” and “documented/stable composition
pattern” are not identical categories here.

## 3. Version Field Semantics: create, read, update, stale-write conflict

### What the project and reference require

- The project’s own test guidance says versioned contracts must support:
  - read returns version `N`
  - update must submit `N`
  - successful update returns `N+1`
  - stale update returns `409 Conflict`
  ([AGENTS.md](/home/nes/discord/AGENTS.md:146)).
- The Java reference tests exercise exactly that shape
  ([TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:136),
  [TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:307),
  [TestAuditInfo.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/audit/TestAuditInfo.java:141)).

### What the reference also shows about creation

- In the Java reference, create payloads in controller and service tests
  often still include `version(0L)` for newly created DTOs
  ([TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:87),
  [TestTesterController.java](/home/nes/discord/.refs/java-interview-setup/src/test/java/com/real/interview/controller/TestTesterController.java:103)).
- That is different from a contract shape where create omits version
  entirely or uses `null`.

### What FastAPI documents about schema semantics

- With Pydantic v2, FastAPI may generate separate OpenAPI schemas for
  the same model used as input vs output when fields have defaults
  ([FastAPI separate input/output schemas](https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/)).
- FastAPI’s example shows that a field with `= None` is not required in
  input, but becomes required in output because the response always
  carries a value, even if that value is `null`
  ([FastAPI separate input/output schemas](https://fastapi.tiangolo.com/how-to/separate-openapi-schemas/)).

### Local runtime observations (`pydantic 2.13.0`)

- A required integer version field produces one obvious request-side
  schema shape: `required + integer + minimum`.
- A nullable defaulted field produces a different request-side schema:
  non-required + `integer | null`.

### Problem-space consequence

The key contract question is not only whether version exists, but
whether the public schema wants to express:

- create payloads that always carry an explicit initial version
- create payloads that may omit version
- a shared model reused for both reads and writes
- different schemas across create, update, and read paths

FastAPI and Pydantic make those choices externally visible in OpenAPI,
not just internally visible in validation code.

## 4. Discord-Specific Entities That Appear Likely to Need Versioned Contracts

### Entities already evidenced in the repo

- `submissions` are long-lived mutable records with workflow state and
  review metadata:
  `status`, `thread_id`, `claimer_id`, `decided_by`, `decided_at`,
  `decision_reason`, `answers_json`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:121)).
- `tickets` are also mutable workflow records with claim/close state:
  `status`, `thread_id`, `claimer_id`, `closed_at`, `closed_by`,
  `subject`, `initial_description`
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:138)).
- `chapters` carry mutable provisioning metadata:
  channel IDs, role IDs, form path, and archive lifecycle fields
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:106)).
- The CLI and daemon are expected to share the same SQLite state, so
  concurrent mutation pressure is already part of the project’s stated
  operating model
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:193)).

### Workflow evidence around applications and tickets

- Applications are explicitly multi-stage review objects:
  `pending -> claimed -> interview -> approved/denied/waitlisted`
  ([research/02-humility-needs.md](/home/nes/discord/research/02-humility-needs.md:47)).
- Tickets have multiple workflow variants and long-lived retention
  requirements
  ([research/02-humility-needs.md](/home/nes/discord/research/02-humility-needs.md:63)).
- The daemon design’s per-item flow for both applications and tickets
  includes queue messages, private threads, claim transitions, and final
  approval/denial/close actions
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:41)).

### Problem-space consequence

Based on the current repo evidence, the strongest candidates for
versioned contracts are the entities where two actors or processes can
race on mutable workflow state:

- application submissions
- tickets
- chapter metadata or chapter-scoped configuration edited from more than
  one surface

By contrast, some entities currently look more append/remove keyed than
versioned, for example `chapter_blacklist`, whose schema is modeled as a
composite-key table rather than a mutable workflow aggregate
  ([docs/DAEMON_DESIGN.md](/home/nes/discord/docs/DAEMON_DESIGN.md:155)).

## 5. Pydantic v2 Best Practices Relevant to This Module

### Field declaration and constraints

- Pydantic documents the normal assignment form as important when using
  `Field(default=...)`, `default_factory`, or `alias`, because static
  type checkers synthesize `__init__` from that form; the annotated-only
  metadata pattern is not understood by type checkers in the same way
  ([Pydantic fields docs](https://docs.pydantic.dev/latest/concepts/fields/)).
- `Field()` constraints affect both validation and generated JSON Schema
  ([Pydantic fields docs](https://docs.pydantic.dev/latest/concepts/fields/)).

### Configuration

- `model_config = ConfigDict(...)` is the documented model-level
  configuration surface
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).
- Custom parent `BaseModel` classes are the documented way to inherit
  shared configuration, and subclass config is merged with parent config
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).
- Multiple-base config has a documented caveat because Pydantic does not
  currently follow Python MRO there
  ([Pydantic config docs](https://docs.pydantic.dev/latest/concepts/config/)).

### Validators

- `field_validator()` can target multiple fields or all fields via `'*'`
  and can be defined on base classes for subclass fields when
  `check_fields=False`
  ([Pydantic validators docs](https://docs.pydantic.dev/latest/concepts/validators/)).
- Default values are not validated unless `validate_default=True` is set
  on the field or via config
  ([Pydantic fields docs](https://docs.pydantic.dev/latest/concepts/fields/)).

### JSON Schema and OpenAPI

- Pydantic JSON schemas are compliant with JSON Schema Draft 2020-12 and
  OpenAPI 3.1
  ([Why use Pydantic](https://docs.pydantic.dev/latest/why/);
  [Pydantic JSON Schema docs](https://docs.pydantic.dev/latest/concepts/json_schema/)).
- `BaseModel.model_json_schema()` is the core API for inspecting the
  emitted schema surface
  ([Pydantic JSON Schema docs](https://docs.pydantic.dev/latest/concepts/json_schema/)).
- Extra schema metadata can be attached at the model level with
  `json_schema_extra`, including examples
  ([FastAPI request example docs](https://fastapi.tiangolo.com/tutorial/schema-extra-example/)).
- FastAPI also supports field-level `examples` and body-level
  `openapi_examples`, which affects how the contract is presented in the
  generated API docs
  ([FastAPI request example docs](https://fastapi.tiangolo.com/tutorial/schema-extra-example/)).

## Summary of the Problem Space

The evidence converges on five facts:

1. In this project, version is intended to be part of the public
   contract, not just an internal repository detail.
2. In the Java reference, version is a non-null primitive carried by
   DTOs, checked on update, and tied directly to `409 Conflict` on stale
   writes.
3. In Pydantic v2, required-vs-defaulted version fields produce
   different validation behavior and different OpenAPI schemas.
4. The documented inheritance/config surface in Pydantic favors
   `BaseModel` parents, while multiple-base composition carries an
   explicit caveat.
5. The Humility domain already has several mutable Discord-facing
   workflow entities where optimistic locking pressure is plausible:
   submissions, tickets, and chapter metadata/configuration.
