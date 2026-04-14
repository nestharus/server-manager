# Research prompt — Chapter contracts (`services/api/app/contracts/chapters.py`)

YOU are the researcher. YOU do the research yourself. Do NOT delegate
to sub-agents or launch subprocesses.

## Task

Research the design space for chapter CRUD contracts (Pydantic schemas)
for the Humility server management API. Chapters are the top-level
organizational unit — each chapter has its own roles, channels, forms,
activity rules, and membership.

## Context

The Humility Discord server management project uses a three-service
architecture with a FastAPI API as the mutation gateway. The API follows
the `ai-workflow` layered pattern with contracts as the API boundary.

Existing contract infrastructure:
- `app/contracts/base.py` — `VersionedMixin(BaseModel)` with
  `version: int = Field(ge=0)` for optimistic locking
- `app/contracts/__init__.py` — re-exports `VersionedMixin`

From DECISIONS.md D4:
- Full application review with multi-question forms per chapter
- Indefinite data retention
- Applications + tickets + chapter provisioning are immediate priorities
- Per-chapter waitlists and activity tracking planned

From proposals/01-v1-scope.md:
- Chapters table: id, name, slug, discord_category_id,
  discord_officer_role_id, discord_member_role_id, status, created_at
- Chapter statuses: active, archived, provisioning
- Each chapter is provisioned by cloning the GUILD TEMPLATE category

## Research questions

1. What Pydantic v2 patterns are appropriate for CRUD contract schemas?
   (separate Create/Read/Update models vs a single model?)
2. How should `VersionedMixin` integrate — which contracts need it?
   (Read and Update need version; Create does not)
3. What validation rules apply to chapter fields?
   - slug: lowercase alphanumeric with hyphens, no spaces
   - name: non-empty, bounded length
   - discord IDs: positive integers (snowflakes)
   - status: enum from a fixed set
4. How do FastAPI/Pydantic best practices handle optional fields for
   partial updates (PATCH)?
5. What patterns from `java-interview-setup` reference (optimistic
   locking, audit info) should inform the contract design?

## Deliverables

Write your findings to `research/26-chapters-contract.md`. Include:
- Pydantic v2 CRUD contract patterns
- VersionedMixin integration strategy
- Validation rules per field
- Partial update patterns
- Java reference pattern applicability
- Discord snowflake ID handling

## Rules

- Do NOT propose solutions or write code
- Do NOT modify any files other than `research/26-chapters-contract.md`
- Do NOT inspect the live Discord server
- Output only the research report
