# Proposal revision prompt — second pass, scope cuts

## Hard rules (read these first)

**YOU are the proposal-revision agent. YOU do the revision yourself.**
Do not launch, spawn, dispatch, or report on any other agent.
There are no subprocesses. There is no orchestrator.

Your deliverable is a full replacement of `proposals/01-v1-scope.md`.

- **DO** read `proposals/01-v1-scope.md` in full before editing.
- **DO** read `risk/01-scope.md` in full and treat it as the binding
  reason for this revision.
- **DO** read `risk/01-audit.md` and `risk/01-shortcut.md` too, but
  use them as constraints to preserve the `LOW` verdicts already won,
  not as a reason to reintroduce heavyweight machinery.
- **DO** read `DECISIONS.md`, `AGENTS.md`, `NOTES.md`,
  `research/01-problem-space.md`, `research/02-humility-needs.md`,
  and `research/04-ocr-backends.md` as grounding context.
- **DO** overwrite `proposals/01-v1-scope.md` with the revised
  proposal.
- **DO NOT** modify any file other than
  `proposals/01-v1-scope.md`.
- **DO NOT** redesign the product. This is a trimming pass, not a
  restart.
- **DO NOT** add compatibility shims, transitional paths, feature
  flags, or "for now" dual behavior.
- **DO NOT** print progress commentary beyond normal agent output.

## Goal

Revise `proposals/01-v1-scope.md` so the next risk pass can clear
`LOW` on the scope axis while preserving the validated shape:

- always-on Discord daemon
- Railway-hosted runtime
- Supabase Postgres as system of record
- Supabase Storage for durable screenshot evidence
- Discord-first operator surface
- applications, activity tracking, tickets, and chapter provisioning
  as the four problem areas

The key framing from the orchestrator is: **take scope's Path A**.
Keep the shape. Cut the weight.

## Required changes

### 1. Keep the four-subsystem shape, but right-size it for Humility

- Do not delete any of the four problem areas.
- Do not add new subsystems.
- Remove "10x Humility" future-proofing where it consumes present-day
  implementation budget without solving a current pain.

### 2. Resolve append-only the Humility-sized way

The first revision leaned into DB-enforced append-only. That helped
audit, but scope is correctly flagging it as heavier than needed for a
single-writer daemon at Humility's scale.

Revise the proposal so that:

- append-only history is enforced at the application/service layer
  plus CI/tests, not by heavyweight DB-trigger machinery
- the proposal states explicitly that v1 assumes a single daemon
  writer plus audited operator commands
- immutable history remains a requirement, but the mechanism is
  proportionate to Humility's actual scale

### 3. Trim tickets to real demand

Revise tickets so that:

- v1 ships `server_support` only
- `moderator` is deferred until the Moderator role is actually staffed
- `chapter_support` and `chapter_incident` are deferred until chapter
  infrastructure exists
- ticket-to-application promotion is removed from v1
- transcript capture is close-time full-history fetch only
- no real-time gateway transcript mirroring or reconciliation remains
  in v1

### 4. Keep OCR in scope, but phase it honestly

Revise activity tracking so that:

- Phase `2a` is upload -> store -> OCR call -> basic extraction
- Phase `2b` is confidence scoring -> fallback OCR/vision ->
  correction UI -> rule evaluation
- Phase `2a` is independently demoable and valuable
- the proposal does not pretend the row parser/correction flow is a
  routine or lightweight deliverable

### 5. Simplify provisioning to a linear audited runner

Revise provisioning so that:

- provisioning remains in scope
- auditability and created-resource ID recording remain in scope
- `provisioning_steps`, automatic resume, automatic rollback, and
  saga-style orchestration are removed from v1
- failure handling becomes sequential execution plus explicit
  human-visible cleanup flow
- the one-time manual first-chapter bootstrap remains an explicit
  dependency

### 6. Trim deployment and ops surface

Revise deployment so that:

- v1 uses one always-on production Railway compute service
- staging validation happens locally against the staging Discord guild
  and staging Supabase, not a second always-on staging Railway
  service
- if you mention staging/prod separation, keep it at the guild /
  database / project level without reintroducing a full second compute
  surface into v1

### 7. Remove dead weight from schema and prose

- Delete or defer tables, fields, and mechanisms whose only consumer
  is a removed v1 feature
- Keep JSONB disciplined and document-shaped
- Avoid "future-proof" structures that only make sense at much larger
  scale

### 8. Preserve the wins from rev1

Do not backslide on the fixes that already brought audit and shortcut
to `LOW`:

- secret scrubbing and logical-only request payload capture
- parameterized SQL
- rate-limit-aware Discord mutation handling
- upload bounds and quotas
- explicit Discord-component fallback to richer web forms if the
  library support is missing
- no SQLite/local-first regression
- no YAML-as-production-source-of-truth regression
- no compatibility shims

## Output requirements

- Overwrite `proposals/01-v1-scope.md`
- Keep the document coherent and internally consistent
- Update sequencing, data model, deployment, anti-scope, and cost
  sections if the required trims change them
- Do not append a changelog or reviewer memo
- Do not create placeholder TODOs

## Success condition

A fresh scope assessor should be able to read the revised proposal and
conclude that the implementation budget now matches Humility's actual
scale while audit and shortcut concerns remain `LOW`.
