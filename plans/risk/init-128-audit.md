READ:
- `proposals/09-receipt-required-submit.md`
- `research/15-receipt-required-submit-problem-map.md`
- `.tmp/rca/member-conversion-FINDINGS.md`
- `/home/nes/ai/workflows/implementation-pipeline.md`
- `proposals/08-applicant-discord-oauth.md`

# INIT-128 Phase 4 - Audit Risk

## Checklist

1. Net-value - PRESENT

   The proposal states a positive net-value case: it reduces the current supported-surface identity risk where public submit accepts anonymous bodies and persists synthetic `public_intake` members, while INIT-127's Discord OAuth receipt exists but is not consumed by submit (`proposals/09-receipt-required-submit.md:31-35`). This is grounded in the RCA, which says INIT-127 is not bound to submit and the public route still creates synthetic applicants (`.tmp/rca/member-conversion-FINDINGS.md:41-47`), and in the problem map's current supported path description (`research/15-receipt-required-submit-problem-map.md:80-97`).

2. Scope + Anti-scope - PRESENT

   Scope explicitly covers cookie path widening, the FastAPI receipt dependency, public endpoint binding, real Discord member resolution, notification event emission, SPA gating, and updated API/web/e2e tests (`proposals/09-receipt-required-submit.md:37-47`). Anti-scope explicitly excludes `member_links`, historical synthetic conversion/repointing, DM materialization or Discord sends, `members.kind` schema changes, Cedar edits, redundant identity headers, officer route changes, retained anonymous submit, and review/channel-management work (`proposals/09-receipt-required-submit.md:49-60`).

3. Supported-surface track - PRESENT

   The required supported-surface dimensions are all present. Deployment mode is local first with remote channels inheriting the same contract (`proposals/09-receipt-required-submit.md:191-194`). Cohort is web applicants on `/applications`, with officers and protected admin paths unaffected (`proposals/09-receipt-required-submit.md:193-195`). Adjacent paths cover INIT-127 OAuth, INIT-124/125A boundary guards, INIT-120 anonymous submit, and Cedar route gating (`proposals/09-receipt-required-submit.md:197-202`). Blast-radius notes cover protected submit, historical `public_intake` rows, notification workers, and absence of Discord-visible writes (`proposals/09-receipt-required-submit.md:204-209`). Migration and rollback are specified both in the supported-surface track and the dedicated rollback section (`proposals/09-receipt-required-submit.md:211-214`, `proposals/09-receipt-required-submit.md:253-274`). Observability is covered through structured 401 codes, real applicant audit actions, and `application.public_submitted` notification events (`proposals/09-receipt-required-submit.md:216-220`).

4. Assumption register - PRESENT

   The proposal has three assumptions, and each includes evidence plus invalidation. A1 covers the HMAC receipt trust boundary with evidence from claim shape, validation, TTL, and cookie attributes, and invalidation by forgery/key leakage/server-side revocation needs (`proposals/09-receipt-required-submit.md:222-224`). A2 covers `INSERT ON CONFLICT DO NOTHING` concurrency with evidence from `members.discord_user_id` uniqueness and `members.kind`, and invalidation by uniqueness semantics changing or bypass writers (`proposals/09-receipt-required-submit.md:225-225`). A3 covers notification event emission without DM materialization, with evidence from existing event/deferred-effect persistence and invalidation if event rows require materialization to count as successful (`proposals/09-receipt-required-submit.md:226-226`).

5. Test-intent track per `implementation-pipeline.md:92` - PRESENT

   The implementation pipeline requires each test group to name the change or verification risk, intended behavior or acceptance condition, selected level, fixture source or fixture application point, assumption link if relevant, expected observable signal, and residual risk (`/home/nes/ai/workflows/implementation-pipeline.md:82-93`). The proposal's test-intent table has columns for all of those fields (`proposals/09-receipt-required-submit.md:228-231`) and supplies fourteen test groups covering receipt rejection, invalid receipts, cookie path delivery, real-member creation/reuse/race handling, non-discord collision rejection, USER authority/audit posture, duplicate client id scoping, notification event emission, SPA gates, web contract changes, and e2e receipt submit (`proposals/09-receipt-required-submit.md:232-245`).

6. Contract specifics - PRESENT

   Cookie path widening is specified as changing `applicant_receipt` from `Path=/applications` to `Path=/` while preserving HttpOnly, Secure, SameSite, and max-age (`proposals/09-receipt-required-submit.md:75-79`). The FastAPI dependency contract is specified as `verify_applicant_receipt(request) -> DiscordIdentity`, including cookie read, error cases, structured 401 body, and success shape (`proposals/09-receipt-required-submit.md:81-101`). The real-member helper contract is specified as `resolve_or_create_real_discord_member`, including snowflake validation, existing-kind checks, `kind='discord'` creation, `INSERT ON CONFLICT DO NOTHING + SELECT`, and aggregate-head/audit invariant preservation (`proposals/09-receipt-required-submit.md:116-130`). The notification event contract is specified as `application.public_submitted` with payload keys and no direct DM send (`proposals/09-receipt-required-submit.md:151-165`).

7. Residual-risk artifact path named - PRESENT

   The proposal names `plans/risk/init-128-test-residuals.md` as the residual-risk artifact and specifies the required residual entry fields when Step 6b cannot verify a named test-intent risk (`proposals/09-receipt-required-submit.md:247-251`).

8. Out-of-scope follow-up - PRESENT

   Follow-up work is explicitly named: BL-018 historical synthetic cleanup, BL-019 chapter management/product links, BL-020 applicant DM materialization, and BL-009 Discord-side queue embeds (`proposals/09-receipt-required-submit.md:276-281`).

## Audit Findings

No blocking audit findings.

Non-blocking observation: the e2e receipt seeding technique is expressed as either a test-helper endpoint or a Playwright-injected test-mode HMAC cookie (`proposals/09-receipt-required-submit.md:70-70`, `proposals/09-receipt-required-submit.md:244-244`). This does not make the proposal incomplete for audit risk because the acceptance condition, fixture surface, observable signal, and residual risk are still named. Phase 5 hookpoint research should select the concrete fixture mechanism before implementation.

## Termination Check

No assumption is invalidated by the supplied inputs. The net-value case remains positive because the current supported path is anonymous synthetic submit (`research/15-receipt-required-submit-problem-map.md:80-87`), the RCA recommends receipt-required submit as the strongest posture (`.tmp/rca/member-conversion-FINDINGS.md:107-119`), and INIT-127 deliberately stopped before requiring receipts on public submit (`proposals/08-applicant-discord-oauth.md:33-38`, `proposals/08-applicant-discord-oauth.md:73-75`).

SUPPORTED_SURFACE_TERMINATION: NONE
VERDICT: LOW
