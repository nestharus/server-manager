READ:
- research/12-discord-side-effects-problem-map.md
- proposals/02-public-application-intake.md
- proposals/18-applications.md
- services/discord/app/handlers/application_submission.py
- services/api/app/services/notifications.py

## Summary

Add a Discord-visible reviewer queue side effect for public web application submissions. When `submit_public_application` creates and routes a public-intake application, the API emits a durable notification event and a Discord-owned side-effect work item. The Discord daemon consumes that work item with the bot identity and posts one review queue embed to a configured application review channel.

This proposal intentionally stops at officer visibility. It does not DM the applicant, does not infer a Discord user from `public:<digest>` synthetic members, and does not add chapter-specific routing or richer web form inputs. The first supported artifact is a queue message that lets officers see that public web intake produced review work.

## Net-value statement

The current public web submit path creates a queued `applications` row, synthetic public-intake applicant, route review row, and audit trail, but no Discord-facing artifact (`research/12-discord-side-effects-problem-map.md`; `services/api/app/services/applications.py`). That leaves officers with no in-Discord signal that public web submissions exist, even though Discord remains the review surface.

The proposal has positive net value if it makes public submissions visible to officers without turning synthetic public applicants into Discord identities. The added blast radius is bounded to one new notification event contract, one Discord queue handler, per-channel review channel config, and tests proving that authenticated Discord submission, review transitions, synthetic-member guards, and public receipt semantics are unchanged.

## Scope

- Emit a durable notification event when `submit_public_application` successfully creates and routes an application.
- Add a Discord side-effect work item keyed by application id so queue posting is retryable and idempotent.
- Add a Discord daemon handler for that work item that posts a reviewer queue embed to one configured review channel.
- Add per-channel runtime config for the review queue channel id through Infisical-backed settings.
- Add observability for event creation, queue post success, queue post retries, definitive failures, and repair targets.
- Add tests that encode the event contract, queue rendering, idempotency, failure handling, config validation, and adjacent-path non-regression.

## Anti-scope

- No chapter selector or richer form inputs.
- No Discord OAuth linking; that belongs to BL-016/BL-017.
- No applicant DMs for unlinked submissions until BL-017 lands.
- No chapter-scoped review channels or multi-chapter routing.
- No public web state-change notification promise beyond the existing web receipt.
- No Discord-side application authoring or editing UX.
- No compatibility shim for legacy SQLite `daemon/applications.py` submission refs.
- No generic notification-rule redesign for embeds, components, or threads in this slice.

## Product decisions to surface

Q: Should public web submissions produce the same reviewer-facing artifact shape as Discord submissions are intended to produce: queue message plus private review thread, or is a simpler designated-channel notification enough for the first slice?

Options A, B, C:

- A. Designated review-channel queue embed only.
  - Tradeoffs: fastest path to officer visibility; avoids private-thread membership ambiguity for synthetic applicants; leaves deeper per-application discussion in follow-up review commands or existing officer workflows.
- B. Queue embed plus private review thread.
  - Tradeoffs: closest to the legacy Discord-first proposal's intended shape (`proposals/18-applications.md`); gives reviewers a per-application workspace; requires clear thread visibility and membership rules that are not currently represented in canonical settings.
- C. Plain text designated-channel notification.
  - Tradeoffs: fits the existing generic notification delivery path (`services/discord/app/handlers/notifications.py`); too weak for a review queue because officers cannot scan status, applicant-support id, or response summary cleanly.

Recommendation: Option A. It reduces the current officer-visibility failure while keeping this slice inside a provable supported surface. Option B is valuable, but private thread membership depends on reviewer identity and permissions that the current service does not model. Option C underuses the application context and would likely be replaced immediately.

Q: Queue message format: embed vs plain text; include form responses inline or link to API/UI; expose the synthetic member id (`public:<digest>`) or hide it behind application id/support id?

Options A, B, C:

- A. Embed with application id, support id, submitted scope, form version, and a short response summary; hide `public:<digest>`.
  - Tradeoffs: readable in Discord; avoids exposing implementation-only synthetic ids; includes enough context for triage without dumping full applicant content into a broad channel.
- B. Embed with all form responses inline.
  - Tradeoffs: convenient for officers; increases PII/content exposure in the queue channel and makes future form expansion risky.
- C. Plain text with synthetic member id and application id.
  - Tradeoffs: easiest to render; leaks an internal identity shape that should remain an API implementation detail.

Recommendation: Option A. The synthetic member exists to satisfy persistence and guard boundaries, not to become a user-facing identifier (`research/12-discord-side-effects-problem-map.md`; `services/api/app/services/members.py`). Officers need the application id/support id, not `public:<digest>`.

Q: If the applicant has no Discord identity, what should the queue message say where a Discord mention would normally appear?

Options A, B, C:

- A. Show "Public web applicant" plus the support id/application id.
  - Tradeoffs: honest about identity state; does not imply the applicant can be pinged; simple to update after BL-017 conversion if desired.
- B. Show the synthetic `public:<digest>` value.
  - Tradeoffs: precise for debugging; confusing to officers and easy to mistake for an addressable Discord identity.
- C. Leave the applicant field blank.
  - Tradeoffs: avoids wrong identity; makes the queue message look broken.

Recommendation: Option A. It preserves product clarity and keeps synthetic identity internals out of the reviewer workflow.

Q: Private review thread membership: officers only, all reviewers with application authority, applicant only after BL-017 linking, or some Cedar-derived reviewer set?

Options A, B, C:

- A. No private thread in this slice; review-channel embed only.
  - Tradeoffs: avoids incorrect reviewer membership while still notifying officers; defers thread membership until reviewer sets are explicit.
- B. Officers-only private thread using parent channel permissions.
  - Tradeoffs: approximates the legacy private-thread workflow; may not actually make the thread visible to all intended reviewers unless Discord permissions include Manage Threads or explicit thread membership.
- C. Applicant joins thread after BL-017 linking.
  - Tradeoffs: supports applicant conversation later; blocked until web submissions can be linked to a real Discord identity.

Recommendation: Option A. A private thread is only useful if the right people can see it. The current canonical settings have no reviewer user set, role recipient model, or Cedar-derived Discord membership projection (`services/discord/app/core/settings.py`; `services/api/app/services/notifications_materialize.py`).

Q: Applicant notifications: no DMs are possible for unlinked synthetic submissions. Should the product promise only web confirmation until linking, send state-change notifications only after conversion, or never backfill historical applicant DMs?

Options A, B, C:

- A. Promise only the web submit confirmation until BL-017 conversion.
  - Tradeoffs: honest and implementable now; applicants do not receive Discord state updates until they link.
- B. Send state-change notifications only after conversion.
  - Tradeoffs: useful later; requires BL-017 to define link records and notification eligibility.
- C. Backfill historical applicant DMs after conversion.
  - Tradeoffs: richer history; can surprise users with delayed messages about old states.

Recommendation: Option A for this slice. Option B should be reconsidered in BL-017. Option C should not be promised unless the product explicitly wants delayed historical notifications.

Q: Should officer notification mention a role, list reviewers, or avoid pings? Current notification materialization supports literal Discord user ids, not role recipients.

Options A, B, C:

- A. Avoid pings in the first slice.
  - Tradeoffs: reduces noise and permission risk; officers must monitor the queue channel.
- B. Mention a configured reviewer role.
  - Tradeoffs: best for urgent visibility; requires role id config, role mention permissions, and product agreement on ping volume.
- C. Mention configured reviewer users.
  - Tradeoffs: precise; creates per-channel user-list maintenance and does not scale to role changes.

Recommendation: Option A. The immediate failure is absence of any queue artifact, not missed push notification. Role/user ping policy should be a separate product decision once submission volume is known.

Q: How much applicant PII/form content is acceptable in Discord-visible messages, especially if the destination channel has broader officer visibility than the eventual private review thread?

Options A, B, C:

- A. Minimal queue content: application id/support id, applicant display placeholder, scope, submitted time, form version, and a truncated response summary.
  - Tradeoffs: enough for triage; limits broad-channel exposure; reviewers may need API/UI access for full details later.
- B. Full form response content in the queue embed.
  - Tradeoffs: maximum convenience; highest exposure and hardest to keep acceptable as the form grows.
- C. Metadata only, no response summary.
  - Tradeoffs: lowest exposure; too little context to tell whether the queue item is actionable.

Recommendation: Option A. It keeps the queue useful without making the review channel the canonical store for applicant content.

## Implementation decisions taken in proposal

AMBIGUOUS: Bot post vs webhook post.

Chosen: bot post.

Justification: the canonical Discord service already runs a bot with guild context and API access (`services/discord/app/__main__.py`; `services/discord/app/core/bot.py`). Bot posting gives one identity for command and side-effect behavior, keeps future thread creation possible, and avoids adding per-channel webhook credentials to Infisical. Webhooks are simpler for one channel message, but they do not align with future bot-owned review actions and private thread work.

AMBIGUOUS: Notification timing: synchronous in submit path, asynchronous via notification event/deferred effect, or replay/eventual from audit log.

Chosen: asynchronous via notification event plus Discord side-effect work item, both created transactionally with the successful public submit.

Justification: public submit must not wait on Discord API latency, but a committed application should not lose its queue request. Emitting the event/work item inside the same database transaction as submit and route keeps durability tied to application creation. The Discord-visible post is retried asynchronously.

AMBIGUOUS: If Discord side-effect creation fails after the application row is queued, should the submit receipt remain success with repair/retry visibility, or should public submit fail?

Chosen: submit receipt remains success once the application is queued; Discord failure is a retryable operational fault.

Justification: the legacy proposal explicitly prefers keeping the persisted submission when Discord handoff fails (`proposals/18-applications.md`). Public web UX should not tell an applicant their application failed after the system accepted and queued it. Operators need observability and repair tooling for the missing queue artifact.

IMPLEMENTATION: Event type and payload contract.

Chosen: emit `application.public_review_requested`.

Justification: `application.submitted` and `application.route` already describe internal lifecycle state. The new event names the product consequence: a public web submission requires Discord reviewer visibility. The event is public-specific so authenticated Discord submissions do not gain new artifacts in this slice.

IMPLEMENTATION: Event emission location.

Chosen: logical ownership stays in `submit_public_application`; the implementation may add an internal post-route hook to `_submit_application_internal` so the event is inserted in the same transaction.

Justification: `submit_public_application` is the public surface that knows this is an unlinked public applicant (`services/api/app/services/applications.py`). The internal helper is allowed as plumbing to avoid a commit-event gap, but the authenticated submit path must not emit this event.

IMPLEMENTATION: Safe payload allowlist.

Chosen: allow only `application_id`, `support_id`, `target_scope_kind`, `target_scope_id`, `form_definition_id`, `form_version`, `submitted_at`, `applicant_display`, `response_summary`, and `source_surface`.

Justification: `notification_events.emit` redacts all non-allowlisted keys (`services/api/app/services/notification_events.py`). The queue embed should not receive raw responses, synthetic member ids, or applicant contact fields.

IMPLEMENTATION: Duplicate/idempotent public submissions.

Chosen: key the Discord side effect by application id and source event id; duplicate public submit responses must not enqueue a second queue post for an existing application.

Justification: public submit already uses `client_application_id` to detect duplicate application creation (`services/api/app/services/applications.py`). Queue posting needs its own idempotency key because Discord message creation is a separate side effect.

IMPLEMENTATION: Generic notification delivery or application-specific handler.

Chosen: application-specific Discord side-effect handler.

Justification: generic notification materialization currently resolves only `discord_user`/`discord_users`, supports `dm` and `designated_channel`, renders plain title/body text, and treats `thread` as out of scope (`services/api/app/services/notifications_materialize.py`; `services/discord/app/handlers/notifications.py`). A queue embed with application-specific fields should not be forced through that generic path.

IMPLEMENTATION: Review destination configuration.

Chosen: per-channel Infisical runtime config, surfaced in Discord settings as `DISCORD_APPLICATION_REVIEW_CHANNEL_ID`.

Justification: existing tests inject `guild.application_review_channel`, but canonical settings do not populate it (`services/discord/app/core/settings.py`; `services/discord/app/handlers/application_review.py`). The review queue destination is runtime environment data, not a notification rule authored through officer CRUD.

IMPLEMENTATION: Local validation with `DISCORD_DRY_RUN=1`.

Chosen: tests validate handler behavior without gateway login, and live local proof requires an explicit runtime toggle before any visible Discord write.

Justification: local GitOps currently sets `DISCORD_DRY_RUN=1`, causing the daemon to prove API reachability and skip gateway login forever (`gitops/channels/local/applications/server-manager/discord-deployment.yaml`; `services/discord/app/__main__.py`). Because posting to Discord is Tier 3, live proof must be a separate approved action.

IMPLEMENTATION: Private-thread permissions.

Chosen: no private thread is created in this proposal, so no new thread permissions are required. The bot settings should still add `SEND_MESSAGES` as a required permission for queue posting.

Justification: existing settings list `MANAGE_ROLES`, `MANAGE_CHANNELS`, and `VIEW_CHANNEL`, but queue posting needs channel send permission (`services/discord/app/core/settings.py`). Thread permission checks belong to the follow-up thread slice.

## Design

### Event emission from `submit_public_application`

`submit_public_application` continues to create or reuse the synthetic public-intake member, map the public payload into `ApplicationSubmission`, and call the existing internal submission lifecycle. After submit plus route succeeds, the public path emits one durable notification event:

```text
event_type: application.public_review_requested
scope_kind: target application scope kind
scope_id: target application scope id
payload:
  application_id: <uuid>
  support_id: <short stable display id derived from application id>
  target_scope_kind: global|chapter|member
  target_scope_id: <nullable>
  form_definition_id: <uuid>
  form_version: <int>
  submitted_at: <iso timestamp>
  applicant_display: Public web applicant
  response_summary: <bounded summary generated from allowed form fields>
  source_surface: api:/api/v1/public/applications
```

The event is emitted with `notification_events.emit(...)` using an explicit allowlist. To avoid a commit-event gap, implementation should add a narrow internal hook so event insertion and side-effect work-item insertion occur inside the same transaction as submit and route. If the hook is not feasible in Phase 5 hookpoint research, the proposal should be revised rather than emitting after commit without idempotent repair.

### New notification event type(s)

Add exactly one event type:

- `application.public_review_requested`: public web submission has reached queued review state and needs one reviewer queue artifact in Discord.

Do not reuse `application.route`: route is a lifecycle transition and can occur for authenticated Discord submissions and future workflows. Do not emit a wildcard event for all application submissions in this slice.

### Discord handler for the new event type

Add an application-specific Discord daemon handler, for example `services/discord/app/handlers/application_queue.py`, that accepts a typed command containing:

- side-effect id,
- event id,
- application id,
- rendered embed payload fields,
- destination channel id,
- idempotency nonce.

Runtime shape:

1. The API writes a Discord side-effect work item with idempotency key `discord:application-public-review-queue:<application_id>`.
2. The Discord daemon runs a narrow background consumer using its API client, claims due `application.public_review_requested` work for subsystem `discord`, and passes the payload to the handler.
3. The handler fetches the configured review channel, posts the embed with a nonce/idempotency marker, and reports success/failure back through the API.
4. The API records Discord message id and delivery status on the side-effect record.

The consumer API must be service-actor only. It should not expose arbitrary deferred-effect mutation to browser or officer clients.

### Channel ID config (per-channel via Infisical)

Add `DISCORD_APPLICATION_REVIEW_CHANNEL_ID` to the Discord runtime settings and local Infisical secret template:

- `services/discord/app/core/settings.py`: required positive integer field.
- `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`: template the secret key from `/runtime/local`.
- `gitops/channels/local/applications/server-manager/discord-deployment.yaml`: pass the env var into the daemon.

Remote channels use the same logical setting under their own Infisical runtime path when remote application workloads are materialized. The code must not branch on `local`.

### Bot vs webhook posting

Use the bot. The handler posts through the Discord bot client using `fetch_channel(DISCORD_APPLICATION_REVIEW_CHANNEL_ID)` and `channel.send(embed=..., nonce=..., enforce_nonce=True)` where the installed discord.py version supports enforced nonces. The visible author is the Humility bot, matching command/review behavior.

No webhook URL is stored. No webhook fallback is added.

### Queue message rendering (embed shape)

The queue message is an embed, not plain text.

Required fields:

- Title: `Public application received`
- Description: `Public web applicant`
- Fields:
  - `Application`: support id and full application id
  - `Scope`: scope kind and scope id or `global`
  - `Form`: form definition id and version
  - `Submitted`: timestamp
  - `Summary`: bounded response summary, truncated by renderer
- Footer: `source: public web intake`

Rendering rules:

- Do not include `public:<digest>`.
- Do not mention a role or user in the first slice.
- Do not include raw full responses.
- Truncate each field to Discord embed limits and apply a total content budget before sending.
- Include a machine-readable marker in the footer or hidden nonce input so repair tooling can correlate message id to application id.

### Private thread (if recommended) — creation + membership

Private thread creation is not recommended for this slice and is not implemented here.

Reasoning:

- Public applicants have no Discord identity until BL-017.
- The canonical Discord settings have no reviewer user list or role-recipient projection.
- Existing generic notification delivery treats thread delivery as out of scope.
- Parent-channel officer visibility is enough to solve the current absence of Discord signal.

The queue embed design should not add fields that imply a thread exists. A later thread proposal can add `discord_review_thread_id` storage and membership rules without changing the event's application id contract.

### Failure handling (Discord post fails after submit succeeds)

Public submit remains successful once the application is queued.

Failure classes:

- Missing channel config: daemon startup/config validation fails before consuming events.
- Channel not found or forbidden: mark the side-effect attempt failed, retry while ambiguous, and expose definitive failure once Discord reports a stable permission/config error.
- Discord HTTP/transient error: retry with bounded attempts.
- Ambiguous post result: retry using idempotency marker/nonce; repair path searches recent channel messages for the marker before posting again.

The repair target is the application id and side-effect id. Operators should be able to see pending/failed Discord side effects through existing deferred-effect/read-model counts or a narrow API read added for this side-effect class.

## Supported-surface track

Deployment mode: local first; remote per-channel config.

- Local adds Infisical and deployment wiring for `DISCORD_APPLICATION_REVIEW_CHANNEL_ID`.
- Local live posting remains blocked by `DISCORD_DRY_RUN=1` until the user explicitly approves a visible Discord write.
- Remote uses the same setting name and side-effect contract when remote channel workloads exist.

Cohort: officers (Discord) + applicants (web).

- Officers receive a Discord queue embed in the configured review channel.
- Applicants receive only the current public web receipt. No Discord applicant notification is promised.

Adjacent paths: INIT-120 public submit, INIT-124/125A guards, Discord submission service (existing).

- INIT-120 public submit keeps the same public route, public actor, synthetic member creation, queued state, and receipt shape (`proposals/02-public-application-intake.md`; `services/api/app/services/applications.py`).
- INIT-124/125A synthetic guards remain unchanged: public-intake members may be applicants through the public path, but are not accepted as real Discord members in roster/trust/owner paths (`research/12-discord-side-effects-problem-map.md`).
- Existing Discord `application_submit` remains authenticated and does not emit `application.public_review_requested` (`services/discord/app/handlers/application_submission.py`).

Blast-radius notes for unchanged adjacent paths:

- `POST /api/v1/applications` is unchanged and remains actor-header based.
- Review commands can continue posting their current plain outcome summaries.
- Interview thread behavior is unchanged.
- Generic notification rule CRUD and plain notification delivery stay unchanged.
- Legacy `daemon/` SQLite submission refs are not read or backfilled.

Migration / rollback:

- Migration is additive: new event type constant/tests, new side-effect records, new Discord setting.
- Rollback disables the Discord side-effect consumer and removes the review channel env var from the daemon.
- Existing applications and notification events remain durable audit facts; rollback does not delete application rows or synthetic members.

Observability:

- Count emitted `application.public_review_requested` events.
- Count pending, delivered, retrying, and failed Discord queue side effects.
- Log correlation id, event id, side-effect id, application id, destination channel id, and Discord message id.
- Readiness should fail or report degraded if the Discord daemon lacks required queue config while queue side effects are enabled.

## Assumption register

A1. Public submit currently creates queued applications but no Discord-visible artifact.

- Evidence: `submit_public_application` maps to `_submit_application_internal` and returns application id; the problem map found no notification event, Discord post, thread creation, or DM in that path (`research/12-discord-side-effects-problem-map.md`; `services/api/app/services/applications.py`).
- Invalidation: Phase 5 hookpoint research finds an already-running queue side-effect path for public submissions.

A2. The notification event substrate is the right durable API-side emission point, but not the right rich Discord renderer.

- Evidence: `notification_events.emit` inserts events with correlation context and enqueues materialization; materialization/delivery are rule/text oriented and thread delivery is out of scope (`services/api/app/services/notification_events.py`; `services/api/app/services/notifications_materialize.py`; `services/discord/app/handlers/notifications.py`).
- Invalidation: generic notification delivery gains embed, component, idempotent queue marker, and thread support before implementation begins.

A3. Public synthetic applicants must not be treated as Discord users.

- Evidence: public-intake members use a synthetic public identity and current Discord DM delivery requires numeric `recipient_discord_id` (`research/12-discord-side-effects-problem-map.md`; `services/discord/app/handlers/notifications.py`).
- Invalidation: BL-017 lands first and public submissions are converted to real Discord-linked applicants before queue posting.

A4. Review channel destination should be runtime per-channel config.

- Evidence: local runtime has bot token/guild id/dry-run but no application review channel id; handlers currently rely on injected `guild.application_review_channel` test attributes (`gitops/channels/local/applications/server-manager/discord-deployment.yaml`; `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml`; `services/discord/app/handlers/application_review.py`).
- Invalidation: Phase 5 finds a canonical API or GitOps channel metadata source already populated with review channel ids.

A5. Bot posting is viable but live local proof requires a visible-write approval.

- Evidence: local daemon runs with `DISCORD_DRY_RUN=1`, and project instructions require explicit approval for visible Discord writes (`gitops/channels/local/applications/server-manager/discord-deployment.yaml`; `AGENTS.md`).
- Invalidation: local validation is redefined to use a staging guild or a pre-authorized runbook in `DECISIONS.md`.

A6. Queue-only first slice is sufficient product value.

- Evidence: the problem map's primary current risk is that officers have no in-Discord trigger for public submissions; private thread and applicant DM paths have unresolved identity/membership issues (`research/12-discord-side-effects-problem-map.md`).
- Invalidation: the user rejects queue-only and requires private threads as part of the first visible side-effect artifact.

## Test-intent track

### Residual-risk artifact

Step 6b MUST emit `plans/risk/init-126-test-residuals.md` if any named test-intent risk below cannot be verified by the test set. Each residual entry must include the residual class, technique attempted or considered, scope, budget or bound, result, remaining residual, invalidating inputs, and whether the residual changes the net-value case.

| Test / group | Change risk | Intended behavior | Level | Fixture source/application point | Assumption link | Observable signal | Residual risk |
|---|---|---|---|---|---|---|---|
| Public review event contract | Event payload leaks synthetic ids/raw responses or omits queue fields | `application.public_review_requested` validates with only allowlisted fields and no `public:<digest>`/raw response payload | unit | notification event contract/fixture derived from public submit service | A2, A3 | Pydantic/contract assertions pass; forbidden payload fields fail or are redacted | Does not prove DB transaction timing |
| Transactional event emission | Application queues but event/work item is lost | Public submit writes application, route row, notification event, and Discord side-effect work item under one correlation/idempotency contract | component | API service DB test around `submit_public_application` | A1, A2 | queued application row, route review row, event row, and one side-effect row exist; duplicate retry creates no second side effect | Does not prove Discord daemon consumes work |
| Existing public receipt preservation | Adding side effects changes applicant-facing API semantics | `POST /api/v1/public/applications` still returns the INIT-120 receipt shape and success after queue acceptance | particular-integration | existing public submit API tests with side-effect assertions added | A1, A6 | HTTP 201 body contains unchanged receipt fields; no Discord result leaks into response | Does not prove live browser flow |
| Discord queue embed renderer | Queue message is unreadable, leaks internals, or exceeds Discord limits | Renderer produces one embed with required fields, bounded summary, no pings, and no synthetic id | unit | `services/discord/app/handlers/application_queue.py` renderer fixtures | A3, A6 | embed snapshot/field assertions pass including truncation cases | Does not prove Discord API accepts the embed |
| Bot handler idempotency | Retries produce duplicate queue messages | Handler uses side-effect id/application id marker and reports delivered message id; ambiguous retry checks marker before reposting | unit/component | fake Discord channel and fake API side-effect client | A5 | one send call across duplicate delivery attempts; delivered message id recorded | Fake channel cannot model all Discord nonce behavior |
| Discord config validation | Daemon silently starts without review channel destination | missing/invalid `DISCORD_APPLICATION_REVIEW_CHANNEL_ID` fails settings construction or marks queue side effects disabled explicitly | unit | `services/discord/app/core/settings.py` settings fixtures | A4 | validation error names missing env var; valid positive integer loads | Does not prove Infisical secret exists |
| Local GitOps config wiring | Runtime secret/deployment omits channel id | local rendered manifests template/pass `DISCORD_APPLICATION_REVIEW_CHANNEL_ID` to the Discord deployment | particular-integration | `gitops/channels/local/applications/server-manager/` kustomize/static render | A4, A5 | rendered secret template and deployment env contain the key; no remote/local code branch exists | Does not prove actual Infisical value is populated |
| Authenticated Discord submit non-regression | Existing `/application_submit` begins emitting public queue events or changes response behavior | Discord command still posts `/api/v1/applications`, uses user actor headers, and returns current ephemeral response strings | component | `services/discord/tests/test_application_submission.py` | A1 | existing assertions still pass; no public event side-effect is invoked | Does not prove future Discord submit queue parity |
| Synthetic guard non-regression | Queue rendering treats public-intake synthetic member as real Discord recipient | no DM/user mention is attempted for public queue events; `public:<digest>` remains absent from Discord payload | particular-integration | public submit DB fixture plus Discord handler command fixture | A3 | fake bot receives channel send only; no `fetch_user`/DM call; payload lacks synthetic id | Does not test BL-017 conversion |
| Failure handling and retry visibility | Discord failure either fails applicant submit or disappears silently | post failure marks side effect retrying/failed with correlation/application id while public submit remains successful | component | fake Discord API errors and side-effect status repository/API fixture | A5 | status transitions and logs/records contain error class, attempt count, application id | Does not prove operator repair UX is sufficient |
| Local live-write proof handoff | Tests claim Discord visibility while `DISCORD_DRY_RUN=1` prevents gateway posting | Step 6c records either approved live Discord post proof or a residual explaining dry-run/approval block | end-to-end | local Discord daemon with explicit Tier 3 approval, or residual artifact | A5 | visible queue message id in configured channel, or `plans/risk/init-126-test-residuals.md` records blocked proof | Requires user-approved visible Discord action |

## Migration / rollback

Migration:

1. Add API event/work-item contract and tests.
2. Add Discord queue renderer/handler tests.
3. Add per-channel `DISCORD_APPLICATION_REVIEW_CHANNEL_ID` settings and local GitOps wiring.
4. Deploy API code that emits `application.public_review_requested` for public submit only.
5. Deploy Discord daemon code with the side-effect consumer still blocked by `DISCORD_DRY_RUN=1` in local.
6. After explicit approval for the visible write, toggle local dry-run or use a pre-authorized runbook to prove one queue post.

Rollback:

1. Disable the Discord side-effect consumer or remove the review channel env var.
2. Keep public submit enabled; accepted applications remain queued in the API.
3. Do not delete `notification_events`, side-effect records, applications, reviews, or synthetic members.
4. If duplicate or bad queue messages were posted, remove or correct them manually under the Tier 3 mutation safety workflow.

Rollback restores the current API-only public submit behavior, including the known officer-visibility gap. That gap should be recorded as the rollback consequence.

## Out of scope for follow-up

- BL-017 conversion service + applicant DMs.
- Chapter-scoped review channels (multi-chapter routing).
- Discord-side application authoring/edit UX.
