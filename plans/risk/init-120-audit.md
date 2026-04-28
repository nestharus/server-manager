READ:
- proposals/02-public-application-intake.md
- research/02-public-application-intake-problem-map.md
- .tmp/rca/public-application-intake-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md

## Inputs read

- Approved proposal: `proposals/02-public-application-intake.md`
- Approved problem map: `research/02-public-application-intake-problem-map.md`
- RCA: `.tmp/rca/public-application-intake-FINDINGS.md`
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`

## Checklist results

| Item | Status | Citation | Audit finding |
|---|---|---|---|
| 1. Net-value statement | PRESENT | `proposals/02-public-application-intake.md:7-9`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` | The proposal includes a qualitative net-value statement. It names the current-state risk on the supported web submit surface, cites the RCA/problem map, and names added blast radius plus migration burden: public POST surface, synthetic member rows, Cedar policy, ingress rate limiting, and day-1 validation obligations. |
| 2. Scope and Anti-scope sections | PRESENT | `proposals/02-public-application-intake.md:11-33`; proposal sufficiency rule at `/home/nes/ai/workflows/implementation-pipeline.md:86-87` | Scope and anti-scope are explicit. The proposal names the public route, contracts, service/repository support, SPA fixture/code changes, Cedar/Kong work, tests, and excludes legacy `/apply`, protected admin changes, Discord-visible side effects, OAuth linking, and compatibility shims. |
| 3. Supported-surface track | PRESENT | `proposals/02-public-application-intake.md:275-325`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88` | The track covers deployment mode (`277-280`), customer cohort (`282-285`), adjacent public/user-reachable paths (`287-293`), unchanged-path blast radius (`295-300`), migration path (`302-310`), rollback path (`312-318`), and observability (`320-325`). |
| 4. Assumption register | PRESENT | `proposals/02-public-application-intake.md:327-339`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:91` | AS-1 through AS-6 each name evidence and an invalidation source/observation. The assumptions cover supported web intake, synthetic member acceptability, global day-1 scope, Cedar public principal support, Kong path-specific binding, and API-backed Discord convergence. |
| 5. Test-intent track | PRESENT | `proposals/02-public-application-intake.md:341-435`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:92` | Each named test group includes change/verification risk, intended behavior, selected level, fixture source/application point, assumption links, expected observable signal, and residual risk. Covered groups include contract validation, synthetic persistence, lifecycle write, audit stamping, unauthenticated route behavior, Cedar policy, Kong/Pomerium binding, SPA contract, and local e2e. |
| 6. Contracts/migrations | PRESENT | Public route and contract file: `proposals/02-public-application-intake.md:13-15`; request/response contract shape: `157-186`; persistence/schema posture: `188-205`; policy/rate-limit deltas: `245-273` | New public request/response contracts are described with route, file, request shape, validation rules, and receipt behavior. The persistence section states no new `applications` FK/state column, uses existing `members` and `applications` constraints, defines synthetic `members.discord_user_id`, status, applicant FK usage, idempotency key behavior, actor fields, and request surface. |
| 7. Residual-risk artifact | PRESENT | `proposals/02-public-application-intake.md:341-345`; Step 6b residual rule at `/home/nes/ai/workflows/implementation-pipeline.md:163-167` | The proposal explicitly requires `plans/risk/init-120-test-residuals.md` if any named test-intent risk cannot be verified, and lists required residual fields. This satisfies the Phase 3 acknowledgment requirement. |
| 8. Out-of-scope follow-up | PRESENT | `proposals/02-public-application-intake.md:443-451` | The proposal lists deferred paths and follow-up ownership: identity/linking, legacy `/apply`, alternate auth models, richer web forms, Discord-visible side effects subject to Tier 3 rules, and remote channel deployment. |

## Notable observations

- The proposal is audit-complete for Phase 3 presence obligations. I found no systemic omission in the required checklist areas.
- There is a localized path consistency issue worth resolving before implementation contracts are cut: the SPA/design/migration path says the web form moves to `/api/public/applications` (`proposals/02-public-application-intake.md:209`, `proposals/02-public-application-intake.md:307`, `proposals/02-public-application-intake.md:420`), while the rate-limit posture and Kong test-intent still name the web-host path as `/api/applications` (`proposals/02-public-application-intake.md:270`, `proposals/02-public-application-intake.md:410`). This does not create a presence failure, but it is a concrete contract alignment issue for Step 6a.
- I found no proposal evidence contradicting the approved problem map assumptions. The proposal's net-value case remains positive on the supported public web submit surface.

## Verdict

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
