# Applications subsystem - sketch

Status: design draft, not implemented. Pending owner review.

## Goal

Replace Gather with a self-hosted guild-application flow that lives in this repo so application forms, review logic, and future automation are versioned alongside the rest of the Humility server-management code.

## Current Findings

- Gather has no visible Discord message footprint in Humility.
- The chapter system exists mostly as scaffolding: roles are present and the `GUILD TEMPLATE` category exists, but the channels are empty and no completed application history was found.
- The user wants a first-party sketch now, with implementation only after the current intended process is clarified.

## Architecture Shift

- Keep `discord_cli.py` as a read-only and maintenance CLI.
- Add a persistent daemon process for interaction handling instead of trying to serve forms from a one-shot CLI invocation.
- The daemon should keep a Discord gateway connection open so it can respond to slash commands, buttons, and modal submissions within Discord's interaction timeout window.

## Forms As Code

- Store application definitions in `forms/*.yaml`.
- Each form should define:
  - Stable form id
  - Display name and summary
  - Questions and input types
  - Validation rules
  - Review destination
  - Reviewer roles
  - Approval and rejection actions
- Keeping forms in YAML makes them diffable, reviewable, and editable through the repo.

## Suggested User Flow

1. Applicant runs `/apply <form-id>` or clicks an application entrypoint.
2. The daemon opens a Discord modal or guided question flow.
3. Submission is stored and posted to a private review surface.
4. Reviewers inspect the answers and use approve or reject actions.
5. The system notifies the applicant and optionally applies role changes.

## Storage Options

### Option A: SQLite

- Simple local persistence.
- Easy to query and reason about.
- Private to the host running the daemon.

### Option B: Hidden Discord log channel

- Every submission is mirrored into a locked `#applications-log` channel.
- Provides built-in remote retention and easy manual review.
- Harder to treat as structured state for automation.

## Recommended v1 Scope

- Capture submissions.
- Post them to reviewers.
- Track review status.
- Leave final role mutation manual in v1.

This keeps the first release low-risk on a server that has no live application traffic.

## Deferred Scope

- Automatic role assignment on approval
- Automatic chapter creation
- Chapter-specific role generation
- Full applicant history and analytics
- Web UI for reviewers

## Open Questions For The Owner

1. What questions does the current Gather form ask?
2. Who should review applications?
3. Which review channel should receive submissions?
4. How are chapters supposed to be created today?
5. Do chapters use global roles or chapter-specific roles?
6. Should the daemon run in a terminal session or as a managed background service?
7. Is SQLite or a hidden Discord log channel preferred for storage?

## Proposed Sequence

1. Clarify the owner questions above.
2. Finalize the form contract.
3. Build the daemon and one application flow.
4. Test in a hidden or staging channel.
5. Retire Gather only after the first-party flow works.
