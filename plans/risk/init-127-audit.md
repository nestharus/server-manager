READ:
- proposals/08-applicant-discord-oauth.md
- research/13-applicant-discord-oauth-problem-map.md
- .tmp/rca/discord-oauth-linking-FINDINGS.md
- /home/nes/ai/workflows/implementation-pipeline.md

## Inputs read

- Proposal: `proposals/08-applicant-discord-oauth.md`
- Problem map: `research/13-applicant-discord-oauth-problem-map.md`
- RCA: `.tmp/rca/discord-oauth-linking-FINDINGS.md`
- Pipeline rules: `/home/nes/ai/workflows/implementation-pipeline.md`

## Checklist results

| Item | Status | Citation | Audit finding |
|---|---|---|---|
| 1. Net-value statement | PRESENT | `proposals/08-applicant-discord-oauth.md:39-41`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90`; RCA missing-surface evidence at `.tmp/rca/discord-oauth-linking-FINDINGS.md:87-115` | The proposal states positive net value and ties it to the missing Discord identity proof needed before later conversion/re-pointing work. It also explicitly preserves INIT-120 anonymous submit while adding only the identity proof surface. |
| 2. Scope + Anti-scope | PRESENT | `proposals/08-applicant-discord-oauth.md:43-64`; proposal sufficiency rule at `/home/nes/ai/workflows/implementation-pipeline.md:86-87` | Scope covers Authentik blueprint entries, Infisical/bootstrap secrets, Pomerium callback routing, API callback/session paths, API settings, SPA submit-time behavior, developer onboarding, and tests. Anti-scope excludes member creation, application re-pointing, synthetic conversion, officer OIDC mutation, public submit contract changes, Cedar applicant principals, broader Discord scopes, Discord-visible side effects, and remote-channel rollout. |
| 3. Supported-surface track | PRESENT | `proposals/08-applicant-discord-oauth.md:174-185`; migration/rollback detail at `proposals/08-applicant-discord-oauth.md:212-232`; pipeline supported-surface requirement at `/home/nes/ai/workflows/implementation-pipeline.md:88-90` and Phase 4 role at `/home/nes/ai/workflows/implementation-pipeline.md:100-104` | The track names deployment mode (`local first`), cohort (`web applicants only`), adjacent paths for officer OIDC, Pomerium routes, INIT-120 public submit, and Authentik blueprint loader, plus blast-radius notes, rollback, and observability. It is grounded in the problem map's local-first/cohort context and adjacent surfaces (`research/13-applicant-discord-oauth-problem-map.md:247-285`, `research/13-applicant-discord-oauth-problem-map.md:321-347`). |
| 4. Assumption register | PRESENT | `proposals/08-applicant-discord-oauth.md:187-191`; pipeline requirement at `/home/nes/ai/workflows/implementation-pipeline.md:91` | A1 through A3 each include evidence and an invalidation condition. They cover Authentik Discord OAuth/source model support, Pomerium callback route capability, and API ownership of the server-side handler. |
| 5. Test-intent track per `impl-pipeline.md:92` | PRESENT | `proposals/08-applicant-discord-oauth.md:193-204`; required fields at `/home/nes/ai/workflows/implementation-pipeline.md:92`; Step 6 preservation/output rules at `/home/nes/ai/workflows/implementation-pipeline.md:146-167` | Every row has the required fields: named risk, intended behavior, selected level, fixture source, assumption link, expected observable signal, and residual risk. The track covers Authentik render, Pomerium route render, token exchange, JWT validation, receipt claims, SPA redirect, SPA receipt handling, and live public-form non-regression. |
| 6. Contract specifics: Authentik blueprint shape, Pomerium route, callback handler steps, receipt format | PRESENT | Authentik shape at `proposals/08-applicant-discord-oauth.md:80-92`; Pomerium route at `proposals/08-applicant-discord-oauth.md:94-104`; callback steps at `proposals/08-applicant-discord-oauth.md:118-131`; receipt format at `proposals/08-applicant-discord-oauth.md:153-172`; problem-map open contract questions resolved by proposal at `research/13-applicant-discord-oauth-problem-map.md:299-311`, `research/13-applicant-discord-oauth-problem-map.md:379-392` | The proposal chooses a separate applicant Authentik Source/Provider/Application, exact `discord_user_id` claim, `identify` scope, `/auth/discord/` Pomerium route to the API, server-side code exchange and ID-token validation, and a short-lived HMAC JWT receipt. Phase 6a should encode the proposal's preferred HTTP-only cookie/session completion path as the concrete contract before Step 6b test generation, because the proposal also mentions a one-time transfer endpoint as a fallback. |
| 7. Residual-risk artifact path named | PRESENT | `proposals/08-applicant-discord-oauth.md:206-210`; Step 6b residual-output rule at `/home/nes/ai/workflows/implementation-pipeline.md:163-167` | The proposal names `plans/risk/init-127-test-residuals.md` and specifies the required residual fields if Step 6b cannot verify a named test-intent risk. |
| 8. Out-of-scope follow-up | PRESENT | `proposals/08-applicant-discord-oauth.md:234-238`; RCA decomposition context at `.tmp/rca/discord-oauth-linking-FINDINGS.md:140-198` | Follow-up ownership is explicit: BL-017 owns member link/conversion and application re-pointing, BL-009 owns Discord-visible side effects after linked-member contracts exist, and INIT-120 submit redirect changes wait for BL-017. |

## Notable observations

- The proposal is audit-complete for the required Phase 3 checklist fields. I found no missing checklist artifact that would block Phase 5 on audit-risk grounds.
- The current problem map required the proposal to choose exact callback ownership, claim name, source/provider shape, scopes, and member-creation boundary (`research/13-applicant-discord-oauth-problem-map.md:348-392`). The proposal makes those choices: API-owned callback, `discord_user_id`, Authentik Discord Source plus separate applicant OIDC Provider/Application, `identify` only, and no BL-016 member/application mutation (`proposals/08-applicant-discord-oauth.md:66-76`).
- The only audit note is contract hygiene for Phase 6a: tests should target one receipt/session transport. The proposal names HTTP-only short-lived cookie as the preferred first implementation and allows a transfer endpoint only if the SPA must read the receipt directly (`proposals/08-applicant-discord-oauth.md:129-131`). That is not enough to raise audit risk, but Step 6a should not pass both options through to the test writer.
- No supported-surface termination trigger is apparent. The RCA confirms the current supported surface lacks Discord OAuth Source, applicant OIDC client, applicant callback, and stable Discord snowflake claim (`.tmp/rca/discord-oauth-linking-FINDINGS.md:106-115`), and the proposal's net-value statement targets exactly that gap without expanding into BL-017 conversion work.

## Verdict

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
