# Proposal revision prompt — apply risk assessment findings

## Hard rules (read these first)

**YOU are the proposal-revision agent. YOU do the revision yourself.**
Do not launch, spawn, dispatch, or report on any other agent.
There are no subprocesses. There is no orchestrator.

Your deliverable is a full replacement of `proposals/01-v1-scope.md`.

- **DO** read `proposals/01-v1-scope.md` in full before editing.
- **DO** read `risk/01-audit.md`, `risk/01-scope.md`, and
  `risk/01-shortcut.md` in full and treat them as binding review input.
- **DO** read `DECISIONS.md`, `AGENTS.md`, `NOTES.md`,
  `research/01-problem-space.md`, `research/02-humility-needs.md`,
  and `research/04-ocr-backends.md` as grounding context.
- **DO** overwrite `proposals/01-v1-scope.md` with the revised
  proposal.
- **DO NOT** modify any file other than
  `proposals/01-v1-scope.md`.
- **DO NOT** rewrite the project from scratch. Preserve the accepted
  architecture shape unless a risk finding specifically requires a
  change.
- **DO NOT** add compatibility shims, transitional code paths,
  feature flags, or "for now" dual behavior.
- **DO NOT** print progress commentary to stdout or any log beyond the
  normal agent output.

## Goal

Revise `proposals/01-v1-scope.md` so the next 3x-risk pass can clear
LOW without changing the core validated direction:

- always-on Discord daemon
- Railway-hosted runtime
- Supabase Postgres as system of record
- Supabase Storage for durable screenshot evidence
- Discord-first operator surface
- applications, activity tracking, tickets, and chapter provisioning
  as the four problem areas

The archive summary from the orchestrator is important: these are
**surgical text edits, not a redesign**.

## Required fixes from risk review

### 1. Audit fixes you must add

Add explicit language in the proposal that:

- `error_text` is sanitized before persistence; secrets, tokens,
  headers, connection strings, and raw tracebacks are scrubbed or
  truncated to application-level context before landing in DB rows or
  logs
- `request_json` stores logical operation parameters only (target IDs,
  intended state, operator context), never raw HTTP payloads, raw
  headers, or vendor request bodies
- structured logs pass through a secret-scrubbing filter before
  serialization or export
- the mutation wrapper includes Discord rate-limit-aware retry and
  backoff, respects `Retry-After`, and uses per-route/paced mutation
  execution for bursty provisioning and reconciliation paths
- a one-line requirement is added that all database writes use
  parameterized queries; no user input is interpolated into SQL

These are contained additions to the existing mutation / observability
/ deployment sections, not new subsystems.

### 2. Scope trims you must make

The scope report requires the proposal to be right-sized for Humility.
Revise the proposal so that:

- v1 tickets ship with `server_support` only
- `chapter_support` and `chapter_incident` are deferred until chapter
  infrastructure exists
- `moderator` is deferred until the Moderator role is actually staffed
- transcript capture is simplified to close-time full-history fetch in
  v1 instead of real-time gateway mirroring plus reconciliation
- the OCR subsystem is explicitly split into two phases:
  `2a` upload/store/Vision/basic extraction and `2b`
  confidence scoring/fallback/correction/rule evaluation
- chapter provisioning is simplified for v1: keep auditability and the
  record of created IDs, but cut heavy enterprise-grade
  resume/rollback machinery if the report says it is unjustified at
  Humility's volume
- the proposal makes the first manual bootstrap dependency explicit
  instead of pretending chapters already exist

Preserve the problem framing. Trim implementation surface.

### 3. Shortcut-risk discipline you must preserve

The revised proposal must remain clean on the shortcut axis:

- no SQLite or local-first fallback
- no YAML-as-production-source-of-truth regression
- no compatibility shims
- no hardcoded OCR thresholds presented as validated design truths;
  if you mention starter values, frame them as implementation-time
  calibration inputs gated by empirical evaluation
- keep JSONB usage disciplined and document-shaped, not as a dumping
  ground for data with known structure

### 4. Discord component fallback must be explicit

The scope report flagged an unverified dependency on newer Discord
modal/component support through `discord.py`. The revised proposal
must state a fallback clearly:

- if the required Discord input components are not actually supported
  through the chosen library, richer web forms move into v1 as the
  replacement operator surface for applications rather than silently
  remaining out of scope

Do not handwave this as "we'll figure it out later."

## Output requirements

- Overwrite `proposals/01-v1-scope.md`
- Keep the document coherent and internally consistent
- Update sequencing, anti-scope, and cost/operational sections if the
  required trims change them
- Do not append a changelog or reviewer memo
- Do not create placeholder TODOs

## Success condition

A fresh risk assessor should be able to read the revised proposal and
conclude that the remaining issues are either already mitigated in the
proposal text or are legitimately LOW severity.
