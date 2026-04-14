# Hookpoint Research: Backend Cleanup

## Scope

Map the backend cleanup proposal onto the existing `infra/` code tree.
Find what's reusable, what needs to change, and what to leave alone.

## Context

Read these files for context:
- `proposals/33-backend-cleanup.md` — the proposal being implemented
- `infra/main.tf` — current backend configuration (the file being changed)
- `infra/environments/staging/terraform.tfvars` — existing staging env
- `infra/environments/production/terraform.tfvars` — existing prod env
- `infra/variables.tf` — variable declarations
- `infra/cluster.tf` — cluster module instantiation

## Deliverable

Write `research/33-hookpoints.md` with:

1. **What already exists**: List every file in `infra/` and describe its
   current role
2. **What needs to change**: Identify which file(s) need modification
   and what specifically changes
3. **What is reusable**: Which files can be left completely untouched
4. **What needs to be created**: New `.tfbackend` files and their
   locations
5. **Conflicts or deletions**: Any files that conflict with the proposal

## Anti-goals

- Do NOT write implementation code
- Do NOT propose changes beyond what the proposal specifies
- Do NOT modify any files

## Output path

Write your findings to: `research/33-hookpoints.md`
