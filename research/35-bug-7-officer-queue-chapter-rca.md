# RCA 35 - BUG-7 officer queue missing chapter-scoped applications

## Symptom + State

After the public chapter-scoped submit, Playwright navigates to `/applications/queue` and waits for `[data-application-id="<id>"]`. It times out because the officer queue API call does not return usable queue data.

Live database state confirms the application exists:

- Application id: `b9b7f729-d9b0-42b6-8236-a4f9159af149`
- Applicant id: `8a4765b4-eb09-44ee-a290-ae2c658f0742`
- `target_scope_kind`: `chapter`
- `target_scope_id`: `chapter-alpha`
- `state`: `queued`
- `owner_id`: null
- `submitted_at`: `2026-05-01 05:23:52.752858+00`
- `form_snapshot.scope_kind`: `global`
- `form_snapshot.target_scope.scope_kind`: `chapter`
- `form_snapshot.target_scope.scope_id`: `chapter-alpha`

Live seeded authority rows also exist for the officer Discord user `210987654321098765`:

- Member id: `e5bb8818-965a-4580-8795-0300007d24d0`
- Member row kind: `discord`
- Active chapter-alpha grant: `f08b1ed5-c10c-4260-91be-043aa4efb391`, `scope_kind=chapter`, `scope_id=chapter-alpha`, permissions `["application.claim", "application.review", "application.approve", "application.message"]`
- Active global grants also exist, including `cd9c1d6f-c41c-412b-8ec1-209dd36a5317` with `["application.claim", "application.review", "application.approve", "application.message"]`

But the seeded officer member and seeded grants have no corresponding `aggregate_heads` rows:

- `aggregate_heads` for member `e5bb8818-965a-4580-8795-0300007d24d0`: missing
- `aggregate_heads` for all five officer authority grants observed: missing
- The repository-equivalent query joining `members` to `aggregate_heads` for Discord user `210987654321098765` returns `0 rows`.

Actual bridge behavior with spoofed Pomerium officer headers:

- `GET /api/v1/me`: `200`, returns `groups=["officers"]` and `discord_user_id="210987654321098765"`.
- `GET /api/v1/web/officer/applications?state=submitted,queued`: `500 Internal Server Error`.
- `GET /api/v1/web/officer/applications?state=submitted,queued&scope_kind=chapter&scope_id=chapter-alpha`: `500 Internal Server Error`.

API logs for the queue call show `_build_officer_actor` fails before list filtering:

```text
app.services.members.DiscordMemberRaceLost
...
app.contracts.members.MemberNotFoundError: member with discord_user_id '210987654321098765' was not found
```

## Investigation Findings

### 1. Officer authority for chapter-alpha

`infra/tests/e2e/tests/19-web-ui.sh:280-287` runs `seed-authority-grants.mjs` twice: once with defaults, then once with `E2E_APPLICATION_SCOPE_KIND=chapter` and `E2E_APPLICATION_SCOPE_ID=chapter-alpha`.

`infra/tests/e2e/lib/seed-authority-grants.mjs:69-123` directly inserts into `members` and `authority_grants`. It does not insert or mutate through `aggregate_heads`.

The raw rows exist, including the chapter-alpha grant, but the aggregate heads are missing.

### 2. Queue endpoint scope filter

`services/api/app/api/v1/endpoints/web.py:172-196` accepts `scope_kind` and `scope_id` query parameters and passes them to `list_applications`.

`services/web/src/api/client.ts:366-378` only sends `state`, `limit`, and `after_id`; it never sends `scope_kind` or `scope_id`.

`services/api/app/services/applications.py:448-456` authorizes an omitted scope as `global`:

- `auth_scope_kind = scope_kind or "global"`
- `auth_scope_id = scope_id if scope_kind is not None else None`

`services/api/app/repositories/applications.py:145-153` only adds SQL scope predicates when `scope_kind` / `scope_id` are non-null. With no scope query, the repository query is not scoped.

In the current live failure, the request never reaches this list branch because actor construction fails first. A chapter-only officer without a global grant would be blocked earlier by the default-global authorization behavior.

### 3. Cedar policy for officer list

`policy/cedar/channels/local/services/server-manager-api/policies.json` has public-intake Cedar policy entries, but no officer application list policy.

`services/api/app/services/authorization.py` only defines `authorize_public_intake`. The officer queue path does not call Cedar. Officer list authorization is implemented by local authority grants via `services/api/app/services/applications.py:403-427`.

### 4. SPA queue page

`services/web/src/features/officer/ApplicationQueueRoute.tsx:54-64` calls `fetchOfficerApplicationQueue({ states, afterId })`.

`services/web/src/features/officer/ApplicationQueueRoute.tsx:185-191` renders queue rows with:

```tsx
data-application-id={application().id}
```

The Playwright selector in `infra/tests/e2e/lib/playwright/browser-flow.mjs:148-149` matches the rendered row shape. The selector is not the root cause for the observed live failure; no row is available because the bridge returns 500.

### 5. Bridge endpoint

`services/api/app/api/v1/endpoints/web.py:87-141` builds the officer actor from Pomerium headers:

- requires `officers` group
- requires valid `x-pomerium-claim-discord-user-id`
- calls `resolve_or_create_real_discord_member`
- returns `ActorIdentity(actor_kind="user", actor_id=<member uuid>)`

The live `/api/v1/me` check proves the Pomerium header parsing path is working. The bridge fails specifically when resolving the Discord member into the repository-backed member read model.

### 6. `list_applications` service

`services/api/app/services/applications.py:403-427` authorizes list access if the actor has any application read-equivalent permission in `APPLICATION_READ_PERMISSIONS`. That includes `application.claim`, `application.review`, and `application.approve`.

`services/api/app/services/applications.py:430-473` then delegates to the repository with the supplied filters. The service can list chapter-scoped applications when called with `scope_kind=chapter&scope_id=<chapter>` and a matching authority grant.

The current live queue call fails before `list_applications` because `_build_officer_actor` cannot resolve the seeded member.

### 7. Database query and bridge response

Database evidence:

- Latest application row exists and is chapter-scoped to `chapter-alpha`.
- Officer member raw row exists.
- Officer chapter-alpha grant raw row exists.
- The same member is invisible to `fetch_member_by_discord_id` semantics because that repository joins `members` to `aggregate_heads`, and the seeded member has no aggregate head.

Bridge evidence:

- `/api/v1/me` returns `200`.
- `/api/v1/web/officer/applications?state=submitted,queued` returns `500`.
- Scoped chapter-alpha variant also returns `500`.
- API traceback points to `resolve_or_create_real_discord_member`, not application list filtering.

### 8. Playwright selector

The selector is correct for the SPA code. `ApplicationQueueRoute.tsx` renders `data-application-id={application().id}` on each queue row, and `services/web/tests/officer-queue.spec.ts:185-188` uses the same row selector shape.

The timeout is downstream of the failed queue load, not an attribute mismatch.

## Root Cause

The e2e authority seed helper creates the officer member and grants with direct SQL projection inserts, but does not create aggregate metadata. The live `members` row for officer Discord user `210987654321098765` exists, but it has no `aggregate_heads` row.

The officer bridge does not use raw `members` rows. `_build_officer_actor` calls `resolve_or_create_real_discord_member`, whose initial lookup uses `fetch_member_by_discord_id`. That repository query joins `members` to `aggregate_heads`. Because the seeded member lacks an aggregate head, the lookup returns no member.

The resolver then attempts to create the member. The raw `members.discord_user_id` unique constraint rejects the insert via `ON CONFLICT DO NOTHING`, so the resolver raises `DiscordMemberRaceLost`. Its race-lost recovery path again uses the same aggregate-head-joined lookup, still cannot see the raw seeded member, and raises `MemberNotFoundError`. FastAPI surfaces that unhandled exception as a 500.

Therefore, the queue does not return the chapter-alpha application because the bridge cannot construct the officer actor. Scope filtering and the SPA row selector are not the immediate failure point.

## Affected Paths

- `infra/tests/e2e/lib/seed-authority-grants.mjs`
- `infra/tests/e2e/tests/19-web-ui.sh`
- `services/api/app/api/v1/endpoints/web.py`
- `services/api/app/services/members.py`
- `services/api/app/repositories/members.py`
- `services/api/app/services/applications.py`
- `services/api/app/repositories/applications.py`
- `services/web/src/api/client.ts`
- `services/web/src/features/officer/ApplicationQueueRoute.tsx`
- `policy/cedar/channels/local/services/server-manager-api/policies.json`

## Intervention Points, Not Fix Proposals

This RCA is not proposing a fix. The intervention points are:

- E2e authority/member seeding path and its interaction with aggregate metadata.
- Officer member resolution path when a raw member row exists without an aggregate head.
- Queue scope contract between the SPA and bridge for chapter-specific officers.
- Test coverage that distinguishes bridge actor construction failure from empty queue responses.
- Cedar/non-Cedar authority boundary documentation for officer list actions.

## Evidence Files

- `.tmp/bug-7-officer-queue-chapter/evidence/db-latest-applications.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/officer-grants.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/officer-aggregate-heads.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/officer-member-repository-visibility.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/me-response.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/bridge-response-default.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/bridge-response-chapter-alpha.txt`
- `.tmp/bug-7-officer-queue-chapter/evidence/api-tail-after-bridge.txt`
