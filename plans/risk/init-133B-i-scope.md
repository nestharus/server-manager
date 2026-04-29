# INIT-133B-i — Scope risk gate

**Verdict:** LOW

## In scope (justified)

- `/applications/queue` Solid route with state toggle, load-more, claim — the queue + claim contract this slice exists to ship.
- `services/web/src/features/officer/ApplicationQueueRoute.tsx` plus `officer.module.css` — the only new feature surface.
- `services/web/tests/officer-queue.spec.ts` — new component coverage matched 1:1 to the new route's auth/list/filter/pagination/claim behaviors.
- `services/api/tests/test_web_officer_applications.py` — new API tests scoped to the new bridge endpoints only.
- `services/api/app/api/v1/endpoints/web.py` — adds `/officer/applications` and `/officer/applications/{id}/claim`. Only new backend code path; required because the core `/api/v1/applications` surface needs an `ActorIdentity` member UUID that a browser cannot supply safely (`services/api/app/api/v1/endpoints/applications/lifecycle.py:91-92`, `services/api/app/api/v1/endpoints/applications/lifecycle.py:140-142`).
- `services/api/app/api/v1/endpoints/me.py` + `contracts/web.py` add `groups` from `x-pomerium-claim-groups` — load-bearing because the SPA must gate the queue UI on officer membership before any data fetch; `me.py` today returns no group claim (`services/api/app/api/v1/endpoints/me.py:18-36`) and the existing Pomerium `jwt_claims_headers` already passes the header through (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:42-46`).
- SPA Solid Router migration mounting `/`, `/applications`, `/admin/chapters` as 1:1 behavioral mirrors of today's vanilla `main.tsx`. Required because (a) AGENTS.md "no parallel systems" prohibits leaving the unmounted `app/router.tsx` + `RuntimeApp.tsx` scaffolding alongside vanilla DOM, and (b) extending `main.tsx` (already 314 lines, three routes) with a fourth queue route plus claim signals would entrench the dual system 133B-ii/iii would inherit.
- Deletions of `services/web/src/RuntimeApp.tsx`, `features/forms/DarkNemesisForm.tsx`, and conditionally `features/forms/{schema.ts, form.module.css}` — directly removes the parallel-runtime and demo-form scaffolding the migration replaces. Not "while we're at it" cleanup; these specific files are the parallel-systems instances called out in `research/19-init-133B-problem-map.md:36-56`.
- Pomerium config update — adds exactly two route protections (`/applications/queue` and `/api/web/officer/`) and inserts them before the existing public catch-all. Does not touch the `/admin` rule, `/auth/discord/` rule, catch-all, or `protected-api.local.humility.local` host (`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:47-68`).
- `client.ts` Zod additions for `ApplicationScope`, `ApplicationRead`, `ApplicationListRead`, transition request/response, `CurrentPrincipal.groups`, applicant Discord identity — directly mirrors the contracts the new route consumes; replaces the existing `router: any` (`services/web/src/app/providers.tsx:24`) which is a Shortcut-gate concern, but here is purely additive type tightening.
- E2E extension of `19-web-ui.sh` + `browser-flow.mjs` for queue/claim assertion — keeps suite count at 19 and layers on top of the existing applicant submit (`infra/tests/e2e/tests/19-web-ui.sh:8-37`); no new e2e test number, no audit of pre-existing pathways.

## Out of scope (deferred or rejected)

- Application detail page + `GET /api/v1/applications/{id}` consumption — INIT-133B-ii.
- Transcript view — INIT-133B-ii.
- Message thread (`GET/POST /messages`) — INIT-133B-iii.
- Transitions other than `claim` (review/approve/deny/waitlist/interview/reactivate/withdraw/reassign) — INIT-133B-iii.
- Discord-visible side effects, channel/DM materialization, applicant DM — BL-009 / BL-020.
- Scope selector, owner/"mine" filter, search, sort, bulk actions, export — anti-scope §8.
- Browser-supplied `X-Actor-Kind` / `X-Actor-Id` headers — explicitly rejected; bridge constructs actor server-side.
- Any change to `services/applications.py`, `repositories/applications.py`, `contracts/applications.py`, or `endpoints/applications/lifecycle.py` — verified absent from §3 modified files; the core list/transition/contract surface is untouched.
- New schema, new permission names, new feature flags, vanilla fallback path — all listed in anti-scope.

## Risk surface

| Area | Pre | Post | Justification |
|---|---|---|---|
| New API routes | 0 (under `/api/v1/web/officer/`) | 2 (list, claim) | Bridge required because core list/transition demand `ActorIdentity` UUID; browser cannot safely supply actor headers. |
| Modified API routes | — | `/api/v1/me` adds `groups` field | SPA needs server-asserted group claim to gate the queue UI; field is additive (default `[]`). |
| Core application backend | List/transition services + repository + contract + lifecycle endpoints | unchanged | Slice strictly reuses INIT-133A list and existing transition service; no edit to `services/applications.py`, `repositories/applications.py`, `contracts/applications.py`, `endpoints/applications/lifecycle.py`. |
| Pomerium routes | `/admin` + `/auth/discord/` + catch-all + protected-api host | + `/applications/queue` + `/api/web/officer/` ahead of catch-all | Two additions, both directly protecting new surfaces; nothing else touched. |
| SPA runtime | Vanilla DOM `main.tsx` plus unmounted Solid scaffold | Solid Router as the only runtime | Required by AGENTS "no parallel systems"; migration covers exactly the three routes today's vanilla file owns. |
| SPA routes | `/`, `/applications`, `/admin/chapters` (vanilla) | same three + `/applications/queue` | No unrelated route refactor. |
| SPA deletions | `RuntimeApp.tsx`, `DarkNemesisForm.tsx`, optional `schema.ts`/`form.module.css` | removed | These are the named parallel-runtime/demo-form instances; not opportunistic cleanup. |
| Test deltas | applicant compat spec, Pomerium static spec, 19-web-ui e2e | + officer-queue spec, + bridge spec, + queue assertion in 19-web-ui | All new tests are 1:1 with new code; no backfill of pre-existing systems. |

## Splittable concerns (if any)

- **Web-officer API bridge as its own INIT** — possible in theory, but the bridge has no honest test surface without a UI consumer (the bridge composes Pomerium + Discord receipt + member resolution; round-tripping it cleanly requires the SPA flow it's built for). Rejecting the split is consistent with INIT-132 and INIT-133A scope verdicts, both of which favored shipping the consumer's prerequisites alongside the consumer when they had no independent value.
- **SPA Solid Router migration as INIT-133B-0** — the most defensible candidate split: a "no behavioral change" migration that mounts `/`, `/applications`, `/admin/chapters` as 1:1 mirrors, then 133B-i layers `/applications/queue` on top. It would shrink this slice's net diff and concentrate review attention. The proposal does not explicitly entertain this, but defends bundling because the migration is *motivated* by the queue route — a behavior-neutral migration is hard to justify on its own. Verdict: not required, but worth noting; if implementation runs over the self-imposed `+1,250` net-line ceiling in §9, this is the natural split.
- **Pomerium config update as its own INIT** — too small to stand alone (two route additions); rejecting the split is correct.

## Verdict reasoning

Each of the three named expansions traces to a hard technical constraint that cannot be deferred without making the queue + claim flow incoherent or dishonest: the auth bridge resolves a security boundary (browser cannot supply trusted actor identity), the Solid Router migration removes the parallel-systems anti-pattern AGENTS.md explicitly prohibits, and the Pomerium update is the only mechanism that gates the new route at the edge. The slice does not touch the core application service, repository, contracts, or lifecycle endpoints — it consumes them as-is, exactly mirroring the discipline INIT-132 and INIT-133A passed under. Backend deltas are confined to one additive `groups` field on `/me` (load-bearing for client-side gating) and two new endpoints under `/api/v1/web/officer/`. Deletions are limited to the named parallel-runtime and demo-form instances rather than opportunistic cleanup. New tests are 1:1 with new code. The diff budget is larger than typical because of the migration, and the proposal acknowledges this with an explicit `+1,250` line ceiling and a self-fail rule that escalates to the auth-bridge split — both of which are appropriate self-discipline. Bundling is correct as written.
