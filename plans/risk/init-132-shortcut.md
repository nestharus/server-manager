# INIT-132 — Shortcut risk gate

**Verdict:** LOW

## S1 — No pagination
**Deferred:** the GET endpoint returns the full transcript with
no `limit` / `cursor` parameters.

**Risk:** an application with thousands of state changes +
messages would return a large body.

**Mitigation:** application lifecycle in this product is
short-lived (submitted → decided in days/weeks). Transcripts
are bounded to ≤ ~50 entries in any realistic case. Adding
pagination later is non-breaking (URL stays the same; new
`?limit=X&cursor=Y` query params can be optional).

Not a shortcut — appropriate for v1.

## S2 — Reuses `read_application_messages` for message-side authz
**Choice:** the transcript service calls
`read_application_messages` to get visibility-filtered messages
+ propagate the forbidden error.

**Risk:** if `read_application_messages` ever changes its
authorization rule, the transcript inherits the change silently.

**Mitigation:** that's the desired behavior — both endpoints
should always agree on who can see which messages. Centralized
authz is a feature, not a bug. The transcript-specific test
group asserts the filtering still applies.

Not a shortcut — deliberate consistency.

## S3 — No notification fanout on transcript reads
**Deferred:** read events don't emit notifications.

**Risk:** none — reads do not need fanout. The substrate emits
fanout on writes, not reads.

Not a shortcut.

## S4 — No export formats
**Deferred:** transcript is JSON-only via the API; no PDF /
text-blob export endpoint.

**Risk:** if compliance ever needs printable transcripts, that's
a separate slice.

**Mitigation:** the JSON shape is sufficient for SPA rendering
and machine consumers. Future export can layer on top of this
endpoint.

Not a shortcut — explicit scope.

## Verdict

LOW — every deferral is bounded and reversible. The substrate
has no hidden assumptions about scale or format.
