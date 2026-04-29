# INIT-131 — Shortcut risk gate

**Verdict:** LOW

## Question: did this slice take a shortcut that defers risk?

### S1 — No notification fanout on message append
**Deferred:** an officer posting `applicant_visible` doesn't yet
trigger a notification event to the applicant. Same for the
reverse direction.

**Risk:** SPA users won't know about new messages until they
poll the GET endpoint.

**Mitigation:** the schema preserves `correlation_id` on every
message row, so a future fanout subscriber can join messages →
notifications cleanly. The substrate is "ready for fanout" by
construction.

Not a shortcut — explicitly out-of-scope per Q6 of the proposal,
documented under future-work.

### S2 — No real-time delivery (WebSocket / SSE)
**Deferred:** SPA must poll GET to discover new messages.

**Risk:** UX latency for the message thread.

**Mitigation:** poll-based delivery is acceptable for v1. Notify
fanout (S1) eventually means the SPA can refresh on receiving a
notification event push. WebSocket can land later without
breaking the API surface.

Not a shortcut — appropriate for v1.

### S3 — Cloned `ticket_messages` pattern instead of generic abstraction
**Choice:** new table + service mirroring tickets rather than
extracting a `messageable_aggregates` abstraction.

**Risk:** future drift between the two substrates if requirements
diverge.

**Mitigation:** two consumers do not warrant abstraction. Drift
is opt-in (one substrate can evolve without breaking the other).
Code duplication is minor (one table + a service of ~150 lines)
and makes the per-aggregate intent explicit at every callsite.

Not a shortcut — deliberate "rule of three" deferral.

### S4 — `application.message` permission not pre-seeded
**Choice:** the new permission is granted per-chapter by chapter
admins via the existing authority-grant flow. No global
pre-seeding.

**Risk:** until a chapter admin grants the permission, no officer
can post messages on that chapter's applications.

**Mitigation:** correct by design. There's no universally-trusted
"officer of every chapter" entity in the system. Pre-seeding
would create a security hole.

Not a shortcut — correct authorization model.

### S5 — `_grant` helper swallows `DuplicateActiveGrantError`
**Test fixture fix:** the `_grant` helper in
`test_application_messages_service.py` now wraps
`grant_authority` in `try/except DuplicateActiveGrantError: pass`.

**Risk:** if a future test relies on `_grant` raising on
duplicate, this swallows the signal.

**Mitigation:** the helper is named `_grant` (private to this
test module). Its callsites only set up fixtures; no assertion
hangs on the error. The exception swallow is annotated with a
load-bearing comment.

Not a shortcut — test-fixture-only idempotency to enable
multi-application setup.

## Verdict

LOW — every deferral is documented out-of-scope and the substrate
preserves the join keys (correlation_id) needed for future
extensions.
