# Proposal prompt — Chapter contracts (`services/api/app/contracts/chapters.py`)

YOU are the proposal writer. YOU write the proposal yourself. Do NOT
delegate to sub-agents or launch subprocesses.

## Task

Write a concrete design proposal for
`services/api/app/contracts/chapters.py` — the Pydantic contract module
for chapter CRUD operations.

## Context

Read these files before writing:
- `research/26-chapters-contract.md` — research findings
- `research/26-chapters-contract-needs.md` — synthesis of needs
- `services/api/app/contracts/base.py` — VersionedMixin
- `services/api/app/contracts/__init__.py` — contracts package

## Proposal requirements

The proposal must specify:

1. **ChapterStatus**: StrEnum with `active`, `archived`, `provisioning`
2. **ChapterCreate(BaseModel)**: name (str, min 1, max 100),
   slug (str, regex validated, max 50). No version, no id, no
   server-assigned fields.
3. **ChapterRead(VersionedMixin)**: all fields — id (int), name, slug,
   status, discord_category_id (int|None), discord_officer_role_id
   (int|None), discord_member_role_id (int|None), created_at (datetime),
   version (from VersionedMixin)
4. **ChapterUpdate(VersionedMixin)**: name (str|None), slug (str|None),
   status (ChapterStatus|None), discord_category_id (int|None),
   discord_officer_role_id (int|None), discord_member_role_id
   (int|None), version (from VersionedMixin, required)
5. **Validation rules**: slug regex, name length bounds, snowflake
   positivity
6. **Anti-scope**: what does NOT belong in this module

## Deliverables

Write the proposal to `proposals/26-chapters-contract.md`. Include:
- Architecture (how it fits in the contracts package)
- Exact class definitions and field specifications
- Validation strategy
- Anti-scope list
- OpenAPI generation considerations

## Rules

- Do NOT write code — describe the design
- Do NOT modify any files other than `proposals/26-chapters-contract.md`
- Do NOT inspect the live Discord server
