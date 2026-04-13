# Audit risk assessment — proposals/01-v1-scope.md

Date: 2026-04-13
Assessor: claude-opus (audit)

## Verdict

**MEDIUM**

The proposal has strong structural controls — bounded mutation wrappers, saga-based provisioning, append-only audit intent, explicit claim-visibility helpers, and OCR hallucination checks — but two specific gaps require small, contained amendments before implementation: (1) no mechanism to prevent secrets from leaking into structured logs, audit event payloads, or exception tracebacks, and (2) no Discord API rate-limit handling or retry/backoff strategy for the bursty mutation paths (provisioning, reconciliation, role assignment). Both are fixable without a rewrite, but both have realistic operational blast radius if left unaddressed.

## Findings

### Finding 1 — Secret leakage into logs and audit events

- **Severity**: MEDIUM
- **Section of proposal**: §9 (Deployment — secrets management), §10 (Observability), §3 (Data model — `audit.audit_events`)
- **Description**: The proposal stores `DISCORD_BOT_TOKEN`, `SUPABASE_SERVICE_KEY`, `GOOGLE_CLOUD_VISION_KEY`, and `GEMINI_API_KEY` as Railway env vars and reads them at runtime. §10 defines structured log fields that do not include secrets. However, `audit.audit_events` has `error_text TEXT` and `request_json JSONB` columns that capture mutation context. The mutation safety wrapper (§8) records a planned event before the operation and a succeeded/failed event after — including the error. An unhandled exception during a Discord REST call, a Supabase client call, or a Google/Gemini HTTP request could include authorization headers, connection strings, or API keys in the traceback string that lands in `error_text`. Similarly, `request_json` captures the request payload, but no boundary is defined between the raw HTTP request and what gets persisted.
- **Why it matters**: A single unhandled exception during an authenticated API call could write a bot token or service key into a Postgres row. Anyone with DB read access — including future web dashboards, log exports, staging snapshots shared for debugging, or a compromised Supabase dashboard session — would see the credential. The bot token grants full Administrator-level access to the live Humility guild. The prior assessment rated this LOW by assuming modern drivers don't echo secrets in errors; that assumption is fragile. `httpx`, `aiohttp`, and `requests` all include the full URL (potentially with query-string API keys) in connection error messages. Google Vision and Gemini client libraries may include auth context in verbose error modes.
- **Recommendation**: Add an explicit requirement that (a) the mutation wrapper sanitizes `error_text` by stripping known secret patterns and truncating raw tracebacks to application-level context, (b) `request_json` captures logical operation parameters (target IDs, intended state), never raw HTTP payloads or headers, and (c) structured log output passes through a secret-scrubbing filter before serialization. This is a small addition to §8 and §10, not a rewrite.

### Finding 2 — No Discord API rate-limit or retry strategy

- **Severity**: MEDIUM
- **Section of proposal**: §7 (Chapter provisioning), §5 (Tickets — transcript reconciliation), §8 (Shared infrastructure — mutation wrapper)
- **Description**: The provisioning saga creates 6 roles, 1 category, multiple channels, applies per-channel overwrites, posts an application panel, and pins it — 15–25+ Discord REST calls in rapid succession. Ticket close-time transcript reconciliation (§5) fetches full thread message history, which can be paginated and bursty. The mutation safety wrapper (§8) records audit events around each call, but no mention is made of handling HTTP 429 responses, implementing exponential backoff, respecting `X-RateLimit-Remaining` headers, or queuing mutations to stay under per-route bucket limits.
- **Why it matters**: Discord rate limits are per-route and per-resource. Role creation, channel creation, and permission overwrite updates each have tight per-guild limits. A provisioning run that hits a 429 without retry logic will leave the saga in a partially completed state with a `failed` step. The saga's resume path handles this, but the operator must manually intervene each time. Worse, if the wrapper retries naively without respecting `Retry-After`, the daemon could be temporarily banned from the route. A reconnect-loop bug (acknowledged in §10 metrics) that triggers reconciliation on each reconnect could amplify rate-limit pressure into sustained API lockout. The prior assessment rated this LOW by noting that saga resume handles failures; that's true for correctness but doesn't address the operational cost of frequent manual resume cycles or the risk of API-level penalties.
- **Recommendation**: Add a requirement that the mutation wrapper includes rate-limit-aware retry with `Retry-After` header respect and per-route queuing. The provisioning saga should describe a pacing strategy (e.g., minimum inter-call delay for bulk create steps). This is a contained addition to §8 and §7.

### Finding 3 — Audit trail append-only claim not enforced at DB level

- **Severity**: LOW
- **Section of proposal**: §3 (Data model — `audit.audit_events`), §9 (Deployment — RLS disabled)
- **Description**: The proposal states `audit.audit_events` is append-only. The schema defines the table with standard columns but no trigger, rule, or `REVOKE UPDATE, DELETE` preventing modification. §9 disables RLS in v1. The daemon's DB connection uses a service role with full DML privileges.
- **Why it matters**: The append-only property is a code convention, not a database constraint. For v1 with a single writer this is acceptable — the convention holds if the code respects it. The risk escalates if a future web dashboard, migration script, or debugging session uses the same connection role.
- **Recommendation**: Accept as written for v1, LOW severity. A `REVOKE UPDATE, DELETE ON audit.audit_events FROM <daemon_role>` during phase 0 implementation would close this cheaply. No proposal amendment required.

### Finding 4 — No explicit image size or dimension limits before preprocessing

- **Severity**: LOW
- **Section of proposal**: §6 (Activity tracking — OCR pipeline steps 1–2)
- **Description**: The OCR pipeline receives an image via slash command, copies it to Supabase Storage, then runs preprocessing that includes 2x upscale. No explicit pixel dimension or file size limit is stated before the upscale step. Discord's practical attachment limit is 25 MB, but a 25 MB PNG could decode to very large pixel dimensions. Upscaling 2x quadruples memory.
- **Why it matters**: §10 says OCR runs in a bounded async task queue with timeouts and exception isolation, so a memory spike kills the task, not the gateway client. The blast radius is bounded. Repeated large uploads could still degrade daemon responsiveness within the task queue.
- **Recommendation**: Accept as LOW given the task isolation in §10. The implementation should add a max pixel dimension check before upscale as a defensive measure. No proposal amendment required.

### Finding 5 — Gemini prompt injection through adversarial image text

- **Severity**: LOW
- **Section of proposal**: §6 (Activity tracking — OCR pipeline step 7)
- **Description**: Gemini fallback receives the original image plus classical OCR text and a strict JSON schema prompt. Adversarial text embedded in a screenshot could attempt to manipulate the Gemini prompt.
- **Why it matters**: The attack surface is narrow: only chapter officers can upload via `/activity upload`. The hallucination controls in step 8 validate output against independent structural evidence — quoted text must exist in OCR source, row counts must be consistent, scores must match format, and rows are checked against roster candidates. A prompt injection that bypasses all four validation layers simultaneously while producing valid JSON matching the strict schema is not a realistic attack.
- **Recommendation**: Accept as LOW. The structural output validation is the correct defense. The implementation should use system-level instructions rather than user-level for the Gemini prompt to further reduce injection surface. No proposal amendment required.

### Finding 6 — Parameterized query requirement not stated

- **Severity**: LOW
- **Section of proposal**: §3 (Data model), §4–§7 (subsystem descriptions)
- **Description**: User-supplied data — application answers, ticket descriptions, in-game names, correction notes — flows into the database. The proposal does not explicitly require parameterized queries or prohibit string interpolation in SQL.
- **Why it matters**: In the Python/Postgres ecosystem, parameterized queries are standard with asyncpg, SQLAlchemy, or psycopg. The risk is that the proposal's silence could allow an ad-hoc implementation using f-strings for query building, especially in the OCR row insertion path where multiple columns come from parsed external input.
- **Recommendation**: Accept as LOW. This is standard engineering practice enforced by library choice. Worth a one-line addition to §8 during any proposal revision: "All database writes use parameterized queries; no user input is interpolated into SQL strings."

### Finding 7 — Staging/production separation relies solely on env var configuration

- **Severity**: LOW
- **Section of proposal**: §9 (Deployment), §11 (Testing strategy)
- **Description**: Production and staging are separated by env vars: different `DISCORD_GUILD_ID`, `SUPABASE_DB_URL`, etc. No runtime guard prevents a misconfigured staging daemon from connecting to production resources.
- **Why it matters**: For a single-developer project this is standard and acceptable. A misconfigured deploy connecting to the production guild with Administrator privileges could execute mutations against real members and channels.
- **Recommendation**: Accept as LOW. A startup validation of `DISCORD_GUILD_ID` against an expected value per deployment target could be added during implementation. No proposal amendment required.

### Finding 8 — Transcript raw_event_json capture scope

- **Severity**: LOW
- **Section of proposal**: §5 (Tickets — transcript persistence), §3 (Data model — `ticket_messages`)
- **Description**: `ticket_messages.raw_event_json JSONB` stores the full Discord gateway event payload for each message. This could contain metadata beyond the thread conversation — nonces, interaction data, and referenced message content from reply chains.
- **Why it matters**: The privacy boundary is the private thread itself: only thread members can post, so `raw_event_json` captures content from participants who consented to the ticket interaction. The data stays in Postgres and is not sent to third parties. No path exists from ticket content to the OCR pipeline or to public channels. The claim-visibility helper limits who can access the thread.
- **Recommendation**: Accept as written, LOW severity. The private thread model is the correct access-control boundary.

## Overall assessment

Two findings are MEDIUM: secret leakage into error paths (Finding 1) and absent Discord rate-limit handling (Finding 2). Both identify specific, realistic operational hazards — a bot token persisted in an audit row from a connection error traceback, or a provisioning saga failing repeatedly mid-run due to unhandled 429s requiring repeated manual resume. Neither requires a proposal rewrite. Finding 1 needs a sanitization requirement added to §8 and §10. Finding 2 needs a rate-limit-aware retry requirement added to §8 and a pacing note in §7.

The remaining six findings are LOW. The proposal's structural defenses — bounded mutation wrapper with pre/post audit events, saga-based provisioning with tracked resume/rollback, OCR hallucination controls validated against independent evidence, claim-visibility helpers for thread membership, explicit per-channel overwrites rather than category inheritance, soft-delete discipline, and async task isolation for OCR — are credible and specific to the risks of running an Administrator-privileged bot on a live guild.

The overall verdict is **MEDIUM** because Findings 1 and 2 require proposal amendments. The amendments are contained additions to existing sections (§7, §8, §10), not architectural changes. Once addressed, the residual risk profile would be LOW.

## What a LOW verdict requires

The verdict would be LOW if: (a) the proposal included an explicit secret-scrubbing requirement for `error_text`, `request_json`, and structured log output, ensuring no secret can persist in any durable store or log stream; and (b) the proposal included a rate-limit-aware retry and pacing requirement for the mutation wrapper and provisioning saga, ensuring Discord 429 responses are handled automatically rather than requiring operator intervention per failed step.
