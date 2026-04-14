# Synthesis: VersionedMixin Needs for Humility

## Context Mapping

The research identifies five problem-space facts. Here's how they map
to Humility's specific needs:

### 1. Version is a public contract field

Humility's API serves both a web UI and the Discord daemon. Both
surfaces can race on mutable workflow state (e.g., two officers
claiming the same application). The version field must appear in
request/response schemas — it's not an internal persistence detail.

### 2. Java reference semantics apply

The `read -> N, update with N -> N+1, stale -> 409` pattern from
java-interview-setup is exactly what Humility needs. Applications
and tickets are long-lived mutable records where stale-write
detection prevents lost updates.

### 3. Required vs optional version matters

For Humility:
- **Response schemas**: version is always present (required int)
- **Update schemas**: version is required (must provide current version)
- **Create schemas**: version should NOT be required — the server
  assigns version 0 on creation

This means `VersionedMixin` needs to work for read/update (required
version) but create schemas will likely omit or override the field.
The simplest approach: mixin provides a required `version: int` field,
and create schemas are separate models that don't inherit the mixin.

### 4. BaseModel parent is the stable pattern

Given the Pydantic MRO caveat on multiple-base config resolution,
`VersionedMixin` should be a `BaseModel` subclass. Concrete contracts
inherit from it. This avoids the undocumented plain-class mixin
behavior and stays on the stable documented surface.

### 5. Target entities

Immediate candidates for `VersionedMixin`:
- **Submissions** (application workflow: pending → claimed → approved/denied)
- **Tickets** (support workflow: open → claimed → closed)
- **Chapters** (provisioning metadata edited from multiple surfaces)

Not candidates:
- `chapter_blacklist` (append/remove, no mutable aggregate)
- Health check response (read-only, no state)

## Gaps

None identified. The research covers the field semantics, mixin
pattern, and entity candidates thoroughly. The module scope is
well-defined: a single `VersionedMixin` class providing a required
`version: int` field with `ge=0` constraint.
