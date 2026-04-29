READ:
- `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md`
- `plans/BACKLOG.md`
- `proposals/02-public-application-intake.md`
- `services/api/app/repositories/members.py`
- `services/api/app/services/members.py`
- `migrations/versions/wu-011_members.py`

# INIT-124 / BL-005 Phase 2.5 - Existing-State Problem Map

Locked direction: implement a query/service-boundary guard for synthetic
public-intake members. Do not add a schema column in this slice; that remains
deferred to BL-008/OAuth linking. The guard should use one shared predicate for
the current discriminator, `discord_user_id LIKE 'public:%'`.

## Touched surface

### Source and schema contract

| Surface | Current state | Citation |
|---|---|---|
| BL-005 backlog entry | Synthetic public-intake rows in `members` are an open high-priority backlog item because roster-facing queries, trust aggregations, and member counts may mix real Discord users with public placeholders. | `plans/BACKLOG.md:144` |
| INIT-120 AS-2 | The accepted identity assumption was "synthetic placeholder member per public submission"; this was explicitly called out as polluting `members` because the schema has only `discord_user_id` and no native anonymous/pending status. | `proposals/02-public-application-intake.md:65`, `proposals/02-public-application-intake.md:69`, `proposals/02-public-application-intake.md:70` |
| Public-intake follow-up scope | Discord OAuth linking/conversion was out of scope for INIT-120 and remains the later identity cleanup path. | `proposals/02-public-application-intake.md:443`, `proposals/02-public-application-intake.md:445` |
| `members.discord_user_id` | The `members` table stores `discord_user_id` as unique text, with no `kind`/discriminator column. | `migrations/versions/wu-011_members.py:17`, `migrations/versions/wu-011_members.py:20`, `migrations/versions/wu-011_members.py:35` |
| `members.status` | Synthetic rows currently must use one of the same statuses as real members: `active`, `suspended`, or `departed`. | `migrations/versions/wu-011_members.py:39` |
| `applications.applicant_id` | Applications require a non-null FK to `members.id`; this is why public submit creates synthetic members rather than writing a separate pending table. | `migrations/versions/wu-022_applications.py:19`, `migrations/versions/wu-022_applications.py:22`, `migrations/versions/wu-022_applications.py:51` |
| `application_reviews.actor_id` | Application reviews store actor identity as text, separate from applicant identity. | `migrations/versions/wu-022_applications.py:120`, `migrations/versions/wu-022_applications.py:126` |
| `activity_actions.actor_id` | Audit/action rows store `actor_kind`/`actor_id` as text and do not require a `members` FK. Synthetic applicants are valid subjects, but public-intake should remain the actor. | `migrations/versions/wu-002_activity_substrate.py:17`, `migrations/versions/wu-002_activity_substrate.py:23` |
| `trust_signals.member_id` | Trust signals FK directly to `members.id`, so synthetic rows can satisfy the schema unless service validation rejects them. | `migrations/versions/wu-030a_trust_signals.py:17`, `migrations/versions/wu-030a_trust_signals.py:19` |
| `roster_entries.member_id` | Roster entries store `member_id` as unconstrained text, not an FK to `members.id`; read-side filtering needs careful join/lookup semantics. | `migrations/versions/wu-007c_roster_foundation.py:17`, `migrations/versions/wu-007c_roster_foundation.py:21` |

### Members repository and service

| Symbol | Current state | Citation |
|---|---|---|
| `_MEMBER_SELECT` | Canonical member projection joins `aggregate_heads` but has no real-member predicate by itself. | `services/api/app/repositories/members.py:10`, `services/api/app/repositories/members.py:18` |
| `fetch_member_by_id()` | Exact UUID lookup, no `public:` filter. Safe as a raw canonical lookup; unsafe only when real-member semantics are expected by the caller. | `services/api/app/repositories/members.py:25`, `services/api/app/repositories/members.py:31` |
| `fetch_member_by_discord_id()` | Exact discord_user_id lookup, no `public:` filter. Needed for both real Discord snowflakes and synthetic public-intake idempotency. | `services/api/app/repositories/members.py:36`, `services/api/app/repositories/members.py:42` |
| `_fetch_member_by_id_for_update()` | Exact UUID lock path for member status mutation, no `public:` filter. | `services/api/app/repositories/members.py:47`, `services/api/app/repositories/members.py:53` |
| `create_or_get_member()` | Reuses existing rows by `discord_user_id`; currently supports real Discord IDs and `public:` IDs through the same path. | `services/api/app/services/members.py:103`, `services/api/app/services/members.py:109` |
| `resolve_or_create_public_intake_member()` | Central source of synthetic members. It derives `discord_user_id=f"public:{digest[:32]}"` and uses `public-intake` service origin metadata. | `services/api/app/services/members.py:167`, `services/api/app/services/members.py:173`, `services/api/app/services/members.py:175` |
| `get_member_by_id()` / `get_member_by_discord_id()` | Authenticated exact reads expose all member-like rows to callers with `member.read`. | `services/api/app/services/members.py:196`, `services/api/app/services/members.py:205` |
| `patch_member_status()` | Exact status mutation can currently target synthetic rows if the caller has `member.write` and a version. | `services/api/app/services/members.py:216`, `services/api/app/services/members.py:223`, `services/api/app/services/members.py:227` |

### Application surfaces

| Symbol | Current state | Citation |
|---|---|---|
| Public endpoint | `POST /api/v1/public/applications` is intentionally unauthenticated at actor-header level and calls the public submit service after public-intake authorization. | `services/api/app/api/v1/endpoints/applications/public.py:18`, `services/api/app/api/v1/endpoints/applications/public.py:26`, `services/api/app/api/v1/endpoints/applications/public.py:29`, `services/api/app/api/v1/endpoints/applications/public.py:32` |
| Authenticated endpoint | `POST /api/v1/applications` requires an actor and calls `submit_application()`. | `services/api/app/api/v1/endpoints/applications/lifecycle.py:30`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:45`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:50`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:53` |
| `_submit_application_internal()` applicant validation | Validates `applicant_id` only by `fetch_member_by_id()`. Because public and authenticated submit share this helper, authenticated submit can currently accept a synthetic applicant UUID if supplied. | `services/api/app/services/applications.py:572`, `services/api/app/services/applications.py:594`, `services/api/app/services/applications.py:595`, `services/api/app/services/applications.py:615` |
| `submit_public_application()` | Creates/reuses a synthetic member and then submits through the shared internal lifecycle with `PUBLIC_INTAKE` authority. This path must keep allowing synthetic applicants. | `services/api/app/services/applications.py:737`, `services/api/app/services/applications.py:751`, `services/api/app/services/applications.py:756`, `services/api/app/services/applications.py:762`, `services/api/app/services/applications.py:767` |
| Application owner reassignment | `reassign` validates `new_owner_id` by exact member lookup only, so a synthetic UUID can become an owner. | `services/api/app/services/applications.py:844`, `services/api/app/services/applications.py:847`, `services/api/app/services/applications.py:849` |
| Application reactivation owner | `reactivate` validates `next_owner_id` by exact member lookup only, so a synthetic UUID can become an owner. | `services/api/app/services/applications.py:850`, `services/api/app/services/applications.py:854`, `services/api/app/services/applications.py:856` |
| `_APPLICATION_SELECT` | Application repository reads applications and aggregate heads only; it does not join `members`. Synthetic applicants are application data, not automatically roster pollution. | `services/api/app/repositories/applications.py:11`, `services/api/app/repositories/applications.py:34` |
| Client idempotency | Duplicate detection is scoped by `(applicant_id, client_application_id)`, which public submit intentionally uses with the synthetic applicant. | `services/api/app/repositories/applications.py:119`, `services/api/app/repositories/applications.py:127` |
| Owner workload query | `list_open_applications_for_owner_ids()` trusts owner UUIDs passed by leadership/succession code; it does not verify owners are real Discord members. | `services/api/app/repositories/applications.py:207`, `services/api/app/repositories/applications.py:218`, `services/api/app/repositories/applications.py:237` |

### Trust surfaces

| Symbol | Current state | Citation |
|---|---|---|
| Trust signal create endpoint | Officer/API path accepts a `TrustSignalCreate` and delegates to `create_trust_signal()`. | `services/api/app/api/v1/endpoints/trust/signals.py:19`, `services/api/app/api/v1/endpoints/trust/signals.py:26`, `services/api/app/api/v1/endpoints/trust/signals.py:34` |
| `create_trust_signal()` | Validates `request.member_id` by exact member lookup only. Synthetic members can receive operator-managed trust signals today. | `services/api/app/services/trust.py:280`, `services/api/app/services/trust.py:302`, `services/api/app/services/trust.py:303`, `services/api/app/services/trust.py:310` |
| Trust compute endpoint | Officer/API path can compute trust for any UUID member accepted by the service. | `services/api/app/api/v1/endpoints/trust/profiles.py:25`, `services/api/app/api/v1/endpoints/trust/profiles.py:31`, `services/api/app/api/v1/endpoints/trust/profiles.py:39` |
| `compute_trust()` | Validates `member_id` by exact member lookup only and can create a profile for a synthetic member. | `services/api/app/services/trust.py:368`, `services/api/app/services/trust.py:375`, `services/api/app/services/trust.py:376`, `services/api/app/services/trust.py:400` |
| Trust recompute endpoint | Officer/API path can recompute trust for any UUID accepted by the service. | `services/api/app/api/v1/endpoints/trust/recompute.py:20`, `services/api/app/api/v1/endpoints/trust/recompute.py:31`, `services/api/app/api/v1/endpoints/trust/recompute.py:39` |
| `_recompute_once()` | Validates `member_id` by exact member lookup only and lists active signals for that member. | `services/api/app/services/trust.py:455`, `services/api/app/services/trust.py:462`, `services/api/app/services/trust.py:463`, `services/api/app/services/trust.py:472` |
| `fetch_trust_profile_by_member_id()` | Profile read is by trust profile table only; no join to real members. | `services/api/app/repositories/trust.py:27`, `services/api/app/repositories/trust.py:33` |
| `list_active_signals_for_member()` | Signal list is by `trust_signals.member_id` only; no join to real members. | `services/api/app/repositories/trust.py:151`, `services/api/app/repositories/trust.py:164`, `services/api/app/repositories/trust.py:165` |

### Leadership, authority, roster, compliance, and aggregate surfaces

| Symbol | Current state | Citation |
|---|---|---|
| `_normalize_holder_id()` | Leadership/authority accepts UUIDs or numeric Discord ID strings, but not `public:<hash>` text directly. A synthetic UUID still passes. | `services/api/app/services/authority.py:131`, `services/api/app/services/authority.py:133`, `services/api/app/services/authority.py:137` |
| `_resolve_member_aliases()` | Expands a UUID to `member.discord_user_id` using `fetch_member_by_id()`. A synthetic UUID expands to `public:<hash>` and flows into grants/tickets/application owner queries. | `services/api/app/services/authority.py:142`, `services/api/app/services/authority.py:150`, `services/api/app/services/authority.py:159`, `services/api/app/services/authority.py:161` |
| Leadership context endpoint | Public API surface under `/api/v1/members/{member_id}/leadership-context`; it delegates to read-model logic that expands aliases. | `services/api/app/api/v1/endpoints/authority/leadership_context.py:19`, `services/api/app/api/v1/endpoints/authority/leadership_context.py:26` |
| `read_leadership_context()` | Calls `_collect_member_aliases()` and then lists grants, applications, and tickets for the aliases. | `services/api/app/services/read_models.py:232`, `services/api/app/services/read_models.py:247`, `services/api/app/services/read_models.py:265`, `services/api/app/services/read_models.py:270` |
| Succession endpoint | Chapter succession plan is a user-reachable officer/admin read path. | `services/api/app/api/v1/endpoints/authority/succession_plan.py:17`, `services/api/app/api/v1/endpoints/authority/succession_plan.py:24` |
| `compute_succession_plan()` | Reads latest roster role holders, normalizes holder IDs, expands aliases, then lists grants/applications/tickets for those holders. | `services/api/app/services/authority.py:479`, `services/api/app/services/authority.py:493`, `services/api/app/services/authority.py:497`, `services/api/app/services/authority.py:527`, `services/api/app/services/authority.py:537` |
| `_ROSTER_ENTRY_SELECT` | Roster entry reads do not join `members`; `member_id` is returned as stored text. | `services/api/app/repositories/roster.py:11`, `services/api/app/repositories/roster.py:21` |
| `create_roster_entry()` API | Officer/API write path creates roster entries through `RosterEntryCreate`. | `services/api/app/api/v1/endpoints/roster.py:143`, `services/api/app/api/v1/endpoints/roster.py:150`, `services/api/app/api/v1/endpoints/roster.py:158` |
| `create_roster_entry()` service | Inserts `request.member_id` without validating it against `members` at all. A synthetic UUID string can be stored as a roster holder. | `services/api/app/services/roster.py:117`, `services/api/app/services/roster.py:124`, `services/api/app/services/roster.py:131` |
| `list_latest_role_holders()` | Succession plans read latest role holders directly from `roster_entries`, with no real-member filter. | `services/api/app/repositories/roster.py:170`, `services/api/app/repositories/roster.py:181`, `services/api/app/repositories/roster.py:187` |
| `list_current_roster_members_by_chapter()` | Compliance enumerates current roster members directly from `roster_entries`, no real-member filter. | `services/api/app/repositories/compliance.py:453`, `services/api/app/repositories/compliance.py:460`, `services/api/app/repositories/compliance.py:464` |
| Scheduled compliance | Worker/officer compliance evaluation loops over the roster enumeration and evaluates every returned member. | `services/api/app/services/compliance.py:769`, `services/api/app/services/compliance.py:791`, `services/api/app/services/compliance.py:805` |
| Compliance review consequence | Review path lists current roster members and can apply `under_review` to the matched roster entry. | `services/api/app/services/compliance_review.py:189`, `services/api/app/services/compliance_review.py:201`, `services/api/app/services/compliance_review.py:207`, `services/api/app/services/compliance_review.py:218` |
| Archive plan active-roster count | Chapter archive planning counts active roster entries directly; synthetic roster entries would inflate this aggregate. | `services/api/app/repositories/archive_queries.py:121`, `services/api/app/repositories/archive_queries.py:127`, `services/api/app/repositories/archive_queries.py:134` |
| Operational overview counts | Operational overview counts applications, tickets, deferred effects, and drift; no production global member count was found. | `services/api/app/services/read_models.py:153`, `services/api/app/services/read_models.py:174`, `services/api/app/services/read_models.py:219`; `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:99` |

### Discord-adjacent surfaces

| Symbol | Current state | Citation |
|---|---|---|
| Discord application submit handler | Resolves the interaction actor through `/api/v1/members/by-discord/{discord_user_id}` and then submits authenticated `/api/v1/applications` as that member. The actor ID comes from Discord and should be numeric. | `services/discord/app/handlers/application_submission.py:29`, `services/discord/app/handlers/application_submission.py:60`, `services/discord/app/handlers/application_submission.py:65`, `services/discord/app/handlers/application_submission.py:75` |
| Discord onboarding handler | Member join uses Discord event `discord_user_id`, creates a member if needed, then computes trust for that real member. | `services/discord/app/handlers/onboarding.py:54`, `services/discord/app/handlers/onboarding.py:62`, `services/discord/app/handlers/onboarding.py:70`, `services/discord/app/handlers/onboarding.py:99` |
| Discord roster sync handler | Resolves roster event `member_discord_user_id` through guild member lookup using `int(user_id)`. A `public:<hash>` value would fail here; guard should happen before synthetic rows generate roster sync events. | `services/discord/app/handlers/roster.py:53`, `services/discord/app/handlers/roster.py:59`, `services/discord/app/handlers/roster.py:65`, `services/discord/app/handlers/roster.py:206` |

## Current supported paths

- Public web application submit is supported and must keep creating/reusing
  synthetic `members` rows. The endpoint is `POST /api/v1/public/applications`
  and calls `submit_public_application()` (`services/api/app/api/v1/endpoints/applications/public.py:18`,
  `services/api/app/api/v1/endpoints/applications/public.py:32`), which
  resolves a `public:` member and submits through the existing lifecycle
  (`services/api/app/services/applications.py:751`,
  `services/api/app/services/applications.py:762`).
- Exact member lookup by UUID and by `discord_user_id` works today for all
  member-like subjects. This is needed by public intake idempotency and by
  existing member read endpoints (`services/api/app/repositories/members.py:25`,
  `services/api/app/repositories/members.py:36`;
  `services/api/app/api/v1/endpoints/members.py:112`,
  `services/api/app/api/v1/endpoints/members.py:130`).
- Authenticated Discord application submit works by resolving a real Discord
  actor ID to a member and posting `/api/v1/applications`
  (`services/discord/app/handlers/application_submission.py:60`,
  `services/discord/app/handlers/application_submission.py:65`).
- Discord onboarding works by looking up or creating a member for a Discord
  join event and then computing trust for that member
  (`services/discord/app/handlers/onboarding.py:54`,
  `services/discord/app/handlers/onboarding.py:70`,
  `services/discord/app/handlers/onboarding.py:99`).
- Application review, owner transitions, trust computation, leadership context,
  succession, roster entry writes, compliance evaluation, and archive planning
  all function today, but they do so without a real-Discord-member guard at the
  boundaries listed above.
- `NEEDS_RESEARCH: no production member-list endpoint or global member_count
  query was found in the Python service search. BL-005 mentions member listing
  and member status counts, but current code appears to expose exact member
  reads and roster/aggregate surfaces rather than a direct member list.`

## Known risky or brittle behavior already present

- Authenticated `POST /api/v1/applications` can accept a synthetic
  `applicant_id` because the shared submit helper only checks that
  `fetch_member_by_id()` returns a row (`services/api/app/services/applications.py:594`).
  Public submit must allow synthetic applicants; authenticated/officer submit
  should not.
- Application owner assignment can be polluted. `reassign` and `reactivate`
  accept `new_owner_id`/`next_owner_id` if the UUID exists in `members`, with no
  synthetic guard (`services/api/app/services/applications.py:847`,
  `services/api/app/services/applications.py:854`).
- Trust signal creation, trust compute, and trust recompute can operate on
  synthetic members because each path validates only existence in `members`
  (`services/api/app/services/trust.py:303`,
  `services/api/app/services/trust.py:376`,
  `services/api/app/services/trust.py:463`).
- Trust profile reads and active-signal lists do not join `members`, so any
  synthetic trust profiles/signals created by the service remain readable and
  recomputable (`services/api/app/repositories/trust.py:27`,
  `services/api/app/repositories/trust.py:151`).
- Leadership alias expansion accepts a synthetic UUID and adds the
  `public:<hash>` string to alias sets, which can affect grant, application,
  and ticket handoff views (`services/api/app/services/authority.py:159`,
  `services/api/app/services/authority.py:161`,
  `services/api/app/services/read_models.py:247`).
- Succession plans can treat a synthetic roster holder as a role holder because
  role holders come from `roster_entries` and are expanded through the same
  alias machinery (`services/api/app/repositories/roster.py:170`,
  `services/api/app/services/authority.py:497`,
  `services/api/app/services/authority.py:527`).
- Roster entry creation has no member validation and `roster_entries.member_id`
  is text. This is the most brittle boundary because read-side joins cannot be
  assumed without first defining whether roster member IDs are UUID strings,
  Discord IDs, or both (`migrations/versions/wu-007c_roster_foundation.py:21`;
  `services/api/app/services/roster.py:131`).
- Compliance enumeration reads current roster entries directly. If a synthetic
  member is inserted into roster entries, scheduled compliance and review
  consequences will treat it as current roster state
  (`services/api/app/repositories/compliance.py:453`,
  `services/api/app/services/compliance.py:791`,
  `services/api/app/services/compliance_review.py:202`).
- Chapter archive planning counts active roster entries directly, so synthetic
  roster entries inflate archive plan counts
  (`services/api/app/repositories/archive_queries.py:121`,
  `services/api/app/repositories/archive_queries.py:134`).
- Member status mutation can target a synthetic row through exact UUID lookup.
  This is less directly tied to roster pollution, but it means synthetic rows
  can be made to look like ordinary active/suspended/departed members in exact
  admin surfaces (`services/api/app/services/members.py:216`,
  `services/api/app/services/members.py:227`).

## Adjacent surfaces inside the blast radius

- Discord submission service: already excludes synthetic members by resolution
  shape. It resolves the interaction actor through a Discord ID endpoint
  (`services/discord/app/handlers/application_submission.py:29`) and posts the
  authenticated application with a user actor derived from that member
  (`services/discord/app/handlers/application_submission.py:75`). The service
  boundary still needs a guard because API callers can bypass the Discord
  handler and supply a synthetic UUID to the authenticated endpoint.
- Audit substrate: public intake should keep `actor_kind="service"` and
  `actor_id="public-intake"` while storing the synthetic member as
  `applications.applicant_id`. This matches INIT-120's audit rule
  (`proposals/02-public-application-intake.md:69`,
  `proposals/02-public-application-intake.md:71`) and the audit schema's text
  actor fields (`migrations/versions/wu-002_activity_substrate.py:23`).
- Application review audit rows: review rows have text actors plus nullable
  `reviewer_id`; synthetic applicants are valid application subjects but should
  not become reviewer/owner actors (`migrations/versions/wu-022_applications.py:120`,
  `migrations/versions/wu-022_applications.py:125`,
  `migrations/versions/wu-022_applications.py:126`).
- Trust profile aggregates: synthetic trust signals/profiles are possible today
  and can affect per-member `signal_summary` during recompute, even though no
  global trust aggregate over all members was found
  (`services/api/app/services/trust.py:472`;
  `.tmp/rca/synthetic-public-member-pollution-FINDINGS.md:103`).
- Roster-derived aggregates: compliance, succession, and archive counts are
  in the blast radius because they enumerate `roster_entries`, not because they
  directly query `members` (`services/api/app/repositories/compliance.py:453`,
  `services/api/app/repositories/roster.py:170`,
  `services/api/app/repositories/archive_queries.py:121`).

## Adjacent public or user-reachable paths

- Public web/API submit: `POST /api/v1/public/applications` must continue to
  insert synthetic applicants (`services/api/app/api/v1/endpoints/applications/public.py:18`,
  `services/api/app/services/applications.py:751`).
- Authenticated application submit: `POST /api/v1/applications` should reject
  synthetic `applicant_id` as defense in depth; only the public route should
  create/use synthetic applicants (`services/api/app/api/v1/endpoints/applications/lifecycle.py:45`,
  `services/api/app/services/applications.py:594`).
- Application lifecycle owner actions: `POST /api/v1/applications/{id}/transitions`
  reaches reassign/reactivate owner validation (`services/api/app/api/v1/endpoints/applications/lifecycle.py:76`,
  `services/api/app/services/applications.py:844`,
  `services/api/app/services/applications.py:850`).
- Member exact reads and member status: `/api/v1/members/by-discord/{discord_user_id}`,
  `/api/v1/members/{member_id}`, and `/api/v1/members/{member_id}/status`
  expose or mutate exact rows to authorized actors (`services/api/app/api/v1/endpoints/members.py:112`,
  `services/api/app/api/v1/endpoints/members.py:130`,
  `services/api/app/api/v1/endpoints/members.py:148`).
- Trust endpoints: `/api/v1/trust/signals`, `/api/v1/trust/compute/{member_id}`,
  `/api/v1/trust/{member_id}`, and `/api/v1/trust/recompute/{member_id}` are
  officer/admin-reachable trust surfaces with no synthetic guard today
  (`services/api/app/api/v1/endpoints/trust/signals.py:19`,
  `services/api/app/api/v1/endpoints/trust/profiles.py:25`,
  `services/api/app/api/v1/endpoints/trust/profiles.py:49`,
  `services/api/app/api/v1/endpoints/trust/recompute.py:20`).
- Roster endpoints: `/api/v1/roster-entries` create/get/transition endpoints
  expose roster state to authorized user actors. Creation is the key insertion
  boundary for synthetic roster pollution (`services/api/app/api/v1/endpoints/roster.py:143`,
  `services/api/app/api/v1/endpoints/roster.py:165`,
  `services/api/app/api/v1/endpoints/roster.py:187`).
- Authority/read-model endpoints: `/api/v1/members/{member_id}/leadership-context`
  and `/api/v1/chapters/{chapter_id}/succession-plan` are user-reachable
  officer/admin read paths that can alias or enumerate synthetic roster holders
  (`services/api/app/api/v1/endpoints/authority/leadership_context.py:19`,
  `services/api/app/api/v1/endpoints/authority/succession_plan.py:17`).
- Discord application commands: current submit/review/waitlist/interview
  handlers call the API as real Discord/user actors. Submit resolves a Discord
  actor ID first, which does not naturally produce `public:` synthetic IDs
  (`services/discord/app/handlers/application_submission.py:60`).
- Discord roster sync: `sync_roster()` expects a Discord member ID and converts
  it with `int(user_id)` during guild resolution. Synthetic IDs should be
  stopped upstream, not handled by Discord mutation code
  (`services/discord/app/handlers/roster.py:59`,
  `services/discord/app/handlers/roster.py:206`).
- `NEEDS_RESEARCH: exact Discord slash-command names/registrations for officer
  and admin command surfaces were not mapped in this phase. The reachable API
  and handler primitives above are enough for the proposal's guard list, but
  command-label documentation may need a separate command registry pass.`

## Deployment mode and cohort

- Deployment mode is local channel first. INIT-120 framed public intake local
  proof as browser-to-local-cluster validation, including the local web host,
  API route, Cedar, database, and audit chain
  (`proposals/02-public-application-intake.md:427`,
  `proposals/02-public-application-intake.md:430`,
  `proposals/02-public-application-intake.md:434`).
- The same fix should apply to all channels through the channel-template
  contract. INIT-120's B4 decision says local receives concrete GitOps
  manifests while remote carries the same logical contract once remote
  application GitOps is materialized; no code path should depend on `local`
  (`proposals/02-public-application-intake.md:141`,
  `proposals/02-public-application-intake.md:143`,
  `proposals/02-public-application-intake.md:145`).
- This slice is code/query/service-boundary behavior, not Discord-visible
  mutation. No Tier 3 Discord action is required for the problem-map phase.

## Open questions for proposal

- Where should the single predicate helper live? Likely
  `services/api/app/services/members.py`, because that module owns member
  business logic and already centralizes public synthetic creation
  (`services/api/app/services/members.py:167`), but proposal should decide
  whether repositories also need a SQL helper for query-boundary filtering.
- Should the predicate accept a `MemberRead`/row object, a `discord_user_id`
  string, or both? The proposal should define the helper signature so service
  callers do not reimplement `startswith("public:")` in multiple places.
- Should the helper name be negative (`is_synthetic_member`) or positive
  (`is_real_discord_member`)? The locked behavior is the same:
  `discord_user_id LIKE 'public:%'` marks synthetic rows.
- Should authenticated `POST /api/v1/applications` explicitly reject a
  synthetic `applicant_id`? Yes, as defense in depth: only the public route
  should submit applications for synthetic applicants. Proposal should define
  the exact error code/status and test contract.
- Should `PATCH /api/v1/members/{member_id}/status` reject synthetic members,
  or remain an exact admin mutation for all member-like records? This is not
  required to stop roster pollution, but it affects whether synthetic rows can
  be presented as ordinary active/suspended/departed members.
- How should roster read-side hardening handle `roster_entries.member_id` as
  `TEXT`? The write boundary can reject synthetic UUID strings immediately, but
  read-side joins need an explicit contract for UUID strings vs Discord ID
  strings before filtering existing polluted rows.
- For trust profile reads, is service-boundary prevention enough, or should
  repository reads also join `members` to hide any pre-existing synthetic trust
  profiles? Proposal should choose based on whether the slice includes
  protection against already-polluted rows.
- For leadership alias expansion, should synthetic UUIDs be rejected as invalid
  leadership targets, or silently omitted from alias expansion? Rejection is
  clearer for direct `/leadership-context` calls; omission may be safer for
  roster-derived succession plans if polluted historical roster rows exist.
- Should application owner queries defensively join owners to real members, or
  is owner assignment validation sufficient? Existing polluted owner IDs would
  still appear without read-side hardening.
- Should public synthetic members ever be valid `actor_id` values? Current
  posture says no: public intake uses service actor `public-intake`, while the
  synthetic member is the applicant subject. Proposal should make that invariant
  explicit for audit/review tests.
