READ:
- plans/BACKLOG.md
- proposals/02-public-application-intake.md
- proposals/18-applications.md
- services/discord/app/handlers/application_submission.py
- services/discord/app/commands/application_submission.py
- services/discord/tests/test_application_submission.py
- services/api/app/services/applications.py
- services/api/app/services/notifications.py
- services/api/app/services/notification_events.py
- services/api/app/services/notifications_materialize.py
- services/api/app/services/notifications_delivery.py
- services/api/app/services/mutations.py
- services/api/app/api/v1/endpoints/applications/public.py
- services/api/app/api/v1/endpoints/applications/lifecycle.py
- services/api/app/services/members.py
- services/api/app/contracts/notifications.py
- services/api/app/repositories/notification_events.py
- services/api/app/repositories/notifications.py
- services/discord/app/handlers/notifications.py
- services/discord/app/handlers/application_review.py
- services/discord/app/handlers/application_interview.py
- services/discord/app/handlers/application_waitlist.py
- services/discord/app/core/bot.py
- services/discord/app/core/settings.py
- services/discord/app/__main__.py
- services/discord/app/contracts/interactions.py
- services/discord/tests/test_notifications.py
- services/api/tests/test_public_intake_submit.py
- services/api/tests/test_public_intake_synthetic_member.py
- services/api/tests/test_applications.py
- services/api/tests/test_roster.py
- services/api/tests/test_trust_signals.py
- services/api/tests/test_leadership_context.py
- gitops/channels/local/applications/server-manager/discord-deployment.yaml
- gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml
- gitops/channels/local/applications/server-manager/kustomization.yaml
- gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml
- gitops/channels/local/applications/server-manager/api-ingress.yaml
- daemon/__main__.py
- daemon/claim.py
- daemon/config.py
- daemon/db.py

## Touched surface

- `services/api/app/services/applications.py`: `submit_public_application` currently creates or reuses a synthetic public-intake member, builds an internal `ApplicationSubmission`, calls `_submit_application_internal(...)` with actor `service/public-intake`, and returns the application id (`services/api/app/services/applications.py:773-805`). BL-009 would likely emit a notification event from this path, or from the shared internal submit path after the `route` transition, so public submissions produce review-side work.
- `services/api/app/services/notification_events.py`: this is the actual event producer substrate. `emit(...)` requires an audit context, redacts payload by explicit allowlist, inserts `notification_events`, and enqueues `notifications_materialize` (`services/api/app/services/notification_events.py:32-84`). It is a stronger hookpoint for event fan-out than `services/api/app/services/notifications.py`, which currently owns notification rule CRUD only (`services/api/app/services/notifications.py:80-201`).
- `services/api/app/services/notifications_materialize.py`: materialization matches enabled rules by exact/wildcard event type plus payload filters, resolves only `discord_user` / `discord_users` recipients, supports `dm` and `designated_channel` destinations, and explicitly treats `thread` as out of scope (`services/api/app/services/notifications_materialize.py:60-133`, `services/api/app/services/notifications_materialize.py:165-262`).
- `services/discord/app/handlers/notifications.py`: current Discord delivery renders plain text from title/body and can send DMs or designated-channel messages. It does not render embeds, buttons, review queue actions, or thread messages; thread delivery is an explicit failure path (`services/discord/app/handlers/notifications.py:20-82`).
- `services/discord/app/handlers/`: a richer queue/thread side-effect path would likely need a new application-specific handler or delivery port. The current application handlers cover slash-command submission, review transitions, interview thread creation, and waitlist/reactivate status posts, but not initial review queue materialization (`services/discord/app/handlers/application_submission.py:47-93`; `services/discord/app/handlers/application_review.py:27-99`; `services/discord/app/handlers/application_interview.py:90-157`; `services/discord/app/handlers/application_waitlist.py:30-93`).
- `gitops/channels/local/applications/server-manager/`: local runtime config has `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, and `DISCORD_DRY_RUN=1`, but no application review channel id or notification-rule seed (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:32-46`; `gitops/channels/local/applications/server-manager/runtime-infisicalsecret.yaml:31-33`; `gitops/channels/local/applications/server-manager/kustomization.yaml:3-22`). A proposal needs a channel-specific destination source.
- Legacy `daemon/` surfaces remain adjacent but not canonical. `daemon/applications.py` is deleted; `daemon/__main__.py` says BL-011 removed the legacy SQLite `/apply` flow and the Postgres-via-API handler is canonical (`daemon/__main__.py:97-100`). `daemon/db.py` still has old submission ref columns/helpers, and `daemon/claim.py` still has private-thread visibility helpers (`daemon/db.py:29-44`, `daemon/db.py:250-267`; `daemon/claim.py:40-71`).

## Current supported paths

- API-backed Discord submission command:
  - `application_submit` is registered as an interaction handler (`services/discord/app/commands/application_submission.py:6-13`).
  - The bot dispatch path defers interactions ephemerally by default and sends the handler response as an ephemeral follow-up unless the result opts out (`services/discord/app/core/bot.py:40-75`; `services/discord/app/contracts/interactions.py:27-32`).
  - `handle_application_submit` defers, resolves the Discord user id through `GET /api/v1/members/by-discord/{discord_user_id}` using service actor headers, then posts `POST /api/v1/applications` with the resolved member id, scope, responses, `client_application_id=envelope.interaction_id`, and user actor headers (`services/discord/app/handlers/application_submission.py:47-77`).
  - On `201`, it returns `Application <id> submitted.`; on duplicate `409 duplicate_application_create`, it returns `Application <id> already submitted.` (`services/discord/app/handlers/application_submission.py:81-93`). Tests pin the ack-before-API behavior, authenticated endpoint path, body, and user actor headers (`services/discord/tests/test_application_submission.py:66-91`).
  - The API endpoint requires actor headers and returns full `ApplicationRead` with ETag (`services/api/app/api/v1/endpoints/applications/lifecycle.py:45-57`). The service writes `application.submit`, then immediately runs the internal `route` transition, yielding `state="queued"` and version 2 (`services/api/app/services/applications.py:596-756`).
  - **NEEDS_RESEARCH:current-rich-discord-submit-flow**: the prompt describes a current Discord-driven path that emits a queue message, creates a private review thread, and sends an ephemeral applicant reply. Current source only supports the ephemeral applicant reply for `application_submit`; no current `services/discord` initial submission handler posts a queue message or private review thread. The rich queue/thread flow exists in the legacy proposal (`proposals/18-applications.md:240-276`, `proposals/18-applications.md:353-383`) and the deleted legacy daemon path, not in the canonical API-backed handler.

- Public web submission:
  - The browser `/applications` form posts `/api/public/applications` with global scope, form responses, and a session-scoped `client_application_id` (`services/web/src/main.tsx:140-160`).
  - `POST /api/v1/public/applications` authorizes `Public::"web-intake.<channel>"`, calls `submit_public_application`, and returns `{message, application_id}` (`services/api/app/api/v1/endpoints/applications/public.py:18-38`; `services/api/app/services/authorization.py:24-39`).
  - `submit_public_application` creates or reuses a synthetic member, maps the public payload into the existing internal submission lifecycle, stamps actor `service/public-intake`, and uses request surface `api:/api/v1/public/applications` (`services/api/app/services/applications.py:153-157`, `services/api/app/services/applications.py:773-805`).
  - Public submit tests verify a queued application row, version 2, a route review row with `service/public-intake`, synthetic `public:` applicant id, and audit actions for `application.submit` and `application.route` under the public surface (`services/api/tests/test_public_intake_submit.py:36-70`, `services/api/tests/test_public_intake_submit.py:140-174`).
  - No code in this path emits `NotificationEventDraft`, creates a `notification_events` row, posts to Discord, creates a thread, or DMs an applicant.

- Existing later Discord review/interview paths:
  - Review command handlers can post plain outcome summaries to `guild.application_review_channel` after claim/approve/deny transitions (`services/discord/app/handlers/application_review.py:27-99`).
  - Interview handling can create or reuse a thread under `guild.application_review_channel`, send an `application_id=...` marker into the thread, then call the API interview endpoint with the thread id (`services/discord/app/handlers/application_interview.py:68-110`, `services/discord/app/handlers/application_interview.py:160-235`).
  - Waitlist handling can post a plain status message to `guild.application_status_channel` or fallback `guild.application_review_channel` (`services/discord/app/handlers/application_waitlist.py:30-93`).
  - These paths are transition-command side effects; they do not solve initial public submit review visibility.

## Known risky or brittle behavior already present

- Officers have no in-Discord trigger for a public web submission. The public path lands in the application lifecycle and audit trail, but no notification event or Discord post is emitted.
- There is a source/proposal mismatch around initial Discord submission side effects. The legacy proposal requires a queue message, private thread, refs persistence, and ephemeral confirmation (`proposals/18-applications.md:262-269`, `proposals/18-applications.md:353-383`), but `daemon/applications.py` was deleted and the canonical API-backed `application_submit` handler does not create those artifacts (`daemon/__main__.py:97-100`; `services/discord/app/handlers/application_submission.py:47-93`).
- Current review channel access is test-shaped. Handlers look for ad hoc attributes like `guild.application_review_channel` / `guild.application_status_channel`; `HumilityBot` does not populate them from settings or API state (`services/discord/app/handlers/application_review.py:27-32`; `services/discord/app/handlers/application_interview.py:52-58`; `services/discord/app/core/settings.py:13-31`).
- Local Discord deployment is dry-run. `DISCORD_DRY_RUN=1` skips gateway login forever after API reachability succeeds, so local-first validation of visible Discord writes requires an explicit deployment/runtime change (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:45-46`; `services/discord/app/__main__.py:101-104`).
- The notification subsystem can deliver plain text to DMs or designated channels, but cannot currently deliver queue embeds, components/buttons, private review threads, or thread-channel notifications. `actionable` is stored on envelopes but the Discord handler does not act on it (`services/api/app/contracts/notifications.py:121-149`; `services/discord/app/handlers/notifications.py:20-82`).
- Synthetic public-intake members have no Discord user to ping or DM. They are deliberately stored as `kind="public_intake"` with `discord_user_id="public:<digest>"` (`services/api/app/services/members.py:179-207`; `services/api/tests/test_public_intake_synthetic_member.py:24-57`). A DM envelope using that value as `recipient_discord_id` would fail numeric parsing in the Discord handler (`services/discord/app/handlers/notifications.py:45-57`).
- Synthetic pollution boundaries are intentional and asymmetric. Public submit may create synthetic applicants (`services/api/tests/test_public_intake_submit.py:36-70`), but authenticated submit rejects synthetic applicants, application ownership rejects synthetic owners, roster creation rejects synthetic members, trust signals reject synthetic subjects, and leadership alias expansion rejects synthetic members (`services/api/tests/test_applications.py:241-260`, `services/api/tests/test_applications.py:392-417`, `services/api/tests/test_applications.py:448-465`; `services/api/tests/test_roster.py:295-318`; `services/api/tests/test_trust_signals.py:183-206`; `services/api/tests/test_leadership_context.py:80-103`).
- Bot permission declarations may be incomplete for the proposed side effects. Settings list `MANAGE_ROLES`, `MANAGE_CHANNELS`, and `VIEW_CHANNEL`, but queue posting and thread messaging also require channel-specific send/thread permissions in Discord (`services/discord/app/core/settings.py:21-31`).

## Adjacent surfaces inside the blast radius

- Notification event substrate: `NotificationEventDraft`, `notification_events`, `notifications_materialize`, `notification_envelopes`, and `notifications_deliver` deferred effects. Event payload allowlists matter because `emit` stores only allowlisted keys (`services/api/app/services/notification_events.py:21-84`).
- Notification rule CRUD and rule matching: rules match event type and payload filters, and `designated_channel` destination ids currently live inside `recipients_json` (`services/api/app/services/notifications.py:80-201`; `services/api/app/services/notifications_materialize.py:60-133`).
- Audit/state-change substrate: submit and route mutations share `mutate_entity`, aggregate heads, `activity_actions`, `activity_state_changes`, request surfaces, and correlation context (`services/api/app/services/mutations.py:58-225`; `services/api/app/services/applications.py:685-756`, `services/api/app/services/applications.py:955-977`).
- Discord application lifecycle handlers: `application_submit`, review, interview, waitlist/reactivate. A new initial queue side effect must not break authenticated `POST /api/v1/applications` or transition command behavior.
- Discord channel/role permissions: the review destination must allow the service identity/bot to post and create/manage private threads if private threads are in scope. Current local manifests do not define an application review channel id or channel permission contract under server-manager GitOps.
- INIT-120 public submit: must keep the public receipt shape, synthetic member creation, Cedar public principal, rate limit, and adjacent authenticated route auth behavior (`services/api/app/api/v1/endpoints/applications/public.py:21-38`; `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-43`).
- INIT-124/125A synthetic guards: synthetic members can be application applicants through the public path, but cannot become roster/trust/owner identities. Discord-visible side effects must not accidentally treat `public:<digest>` as a real Discord snowflake.
- Legacy daemon remnants: `daemon/db.py` has queue/thread ref columns and helpers; `daemon/claim.py` has private-thread membership helpers. These are not in the canonical service path, so reusing them would need an explicit proposal decision rather than an accidental compatibility shim.

## Adjacent public or user-reachable paths

- `web.local.humility.local/applications`: public browser form; submits through `/api/public/applications` (`services/web/src/main.tsx:140-160`).
- `api.local.humility.local/api/v1/public/applications`: direct public API path, protected by Cedar public-intake authorization and Kong rate limiting (`services/api/app/api/v1/endpoints/applications/public.py:21-38`; `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:14-43`).
- `api.local.humility.local/api/v1/applications`: authenticated application submit/read/transition route used by Discord commands and other API clients (`services/api/app/api/v1/endpoints/applications/lifecycle.py:27-97`).
- Discord `application_submit` command: current API-backed applicant-facing submit command (`services/discord/app/commands/application_submission.py:6-13`).
- Discord review commands: `application_claim`, `application_approve`, `application_deny`, `application_interview`, `application_waitlist`, and `application_reactivate` are adjacent because they read/transition the same queued applications and may post follow-up Discord state.
- Discord review/status channel(s): no concrete local channel id is currently wired in server-manager runtime config; tests inject `guild.application_review_channel` and `guild.application_status_channel`.

## Deployment mode and cohort

- Cohort is local first. BL-009 comes from INIT-120 out-of-scope follow-up and the public-intake proposal says local is the first deployment target while remote application workload materialization is deferred (`plans/BACKLOG.md:249-261`; `proposals/02-public-application-intake.md:443-451`).
- Local public API route and rate limit already exist under `gitops/channels/local/applications/server-manager/` (`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml:1-43`; `gitops/channels/local/applications/server-manager/kustomization.yaml:14-20`).
- Local Discord daemon is deployed but dry-run, so gateway-visible behavior is currently disabled in local GitOps (`gitops/channels/local/applications/server-manager/discord-deployment.yaml:29-46`; `services/discord/app/__main__.py:101-104`).
- Each channel needs its own Discord destination ids. Current canonical server-manager runtime config does not expose review channel ids; legacy daemon config had per-chapter `applications_channel_id` (`daemon/config.py:195-237`), but that is not wired into the API-backed Discord service.
- Remote channels should use the same logical contract once their application workloads exist; no source path should branch on `local`.

## Open questions for proposal

- PRODUCT: Should public web submissions produce the same reviewer-facing artifact shape as Discord submissions are intended to produce: queue message plus private review thread, or is a simpler designated-channel notification enough for the first slice?
- PRODUCT: Queue message format: embed vs plain text; include form responses inline or link to API/UI; expose the synthetic member id (`public:<digest>`) or hide it behind application id/support id?
- PRODUCT: If the applicant has no Discord identity, what should the queue message say where a Discord mention would normally appear?
- PRODUCT: Private review thread membership: officers only, all reviewers with application authority, applicant only after BL-017 linking, or some Cedar-derived reviewer set?
- PRODUCT: Applicant notifications: no DMs are possible for unlinked synthetic submissions. Should the product promise only web confirmation until linking, send state-change notifications only after conversion, or never backfill historical applicant DMs?
- PRODUCT: Should officer notification mention a role, list reviewers, or avoid pings? Current notification materialization supports literal Discord user ids, not role recipients.
- PRODUCT: How much applicant PII/form content is acceptable in Discord-visible messages, especially if the destination channel has broader officer visibility than the eventual private review thread?
- AMBIGUOUS: Bot post vs webhook post. This is user-visible identity/product shape and also affects audit attribution, credential storage, Discord permissions, and Cedar/service-identity modeling.
- AMBIGUOUS: Notification timing: synchronous in submit path, asynchronous via notification event/deferred effect, or replay/eventual from audit log. This is partly reliability/implementation and partly user-facing latency/failure semantics.
- AMBIGUOUS: If Discord side-effect creation fails after the application row is queued, should the submit receipt remain success with repair/retry visibility, or should public submit fail? The legacy proposal prefers not losing the application when Discord handoff fails (`proposals/18-applications.md:503-514`), but public web UX may need explicit wording.
- IMPLEMENTATION: What event type and payload contract should represent public application review fan-out, for example `application.submitted_public`, `application.queued`, or reuse `application.route`?
- IMPLEMENTATION: Where should notification events be emitted: inside `_submit_application_internal` for all submit surfaces, only inside `submit_public_application`, or from a replay of `activity_state_changes`?
- IMPLEMENTATION: What payload allowlist is safe and sufficient for notification events? `emit` redacts every payload key not allowlisted.
- IMPLEMENTATION: How should duplicate/idempotent public submissions avoid duplicate Discord messages or threads? Existing submit uses `client_application_id` for duplicate application detection; notification/envelope grouping has separate idempotency keys.
- IMPLEMENTATION: Should this extend the generic notification delivery path, or create an application-specific deferred effect that can post embeds, buttons, and private threads?
- IMPLEMENTATION: Where is the review destination configured per channel: GitOps env/secret, seeded notification rule, chapter/form routing rule, API settings, or Discord-discovered channel metadata?
- IMPLEMENTATION: How does local validation run with `DISCORD_DRY_RUN=1` today? Proposal needs either a dry-run proof artifact or an approved runtime change for live visible writes.
- IMPLEMENTATION: If private threads are in scope, what exact Discord permissions are required and how are they checked before enabling the feature?
