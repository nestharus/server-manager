# Session handoff (2026-04-29 → next session)

Branch: `recovery/test-first-audit` on worktree
`/home/nes/projects/server-manager/worktrees/recovery-test-first-audit`.
HEAD: `ff57385` (BACKLOG close BL-019D-α).
Tree clean.

## What shipped this session

Five INIT slices, each e2e=19/19 on humility-local:

| Commit | INIT | Backlog | What |
|---|---|---|---|
| 19b57b7 | INIT-127 | BL-016 | Authentik Discord OAuth (prior session, listed for context) |
| 98bfa77 | INIT-128 | BL-017 | receipt-required public submit (replaces anonymous flow) |
| dd96473 | INIT-129 | BL-018 | remove dead synthetic-creation path |
| 4b210f6 | INIT-131 | BL-019B | application_messages substrate |
| 3bdbab1 | INIT-132 | BL-019C | transcript endpoint |
| bb5fbc7 | INIT-133A | BL-019D-α | list-applications endpoint |

Plus four BACKLOG-close commits, BL-008 supersession,
BL-019 decomposition + substrate audit.

## What's left

In `plans/BACKLOG.md` priority order:

### Next pick — BL-019D-β / INIT-133B
**SPA officer review surface.** Frontend, multi-hour.

Consumes (now all in place):
- BL-019B: `POST/GET /api/v1/applications/{id}/messages` —
  visibility=`applicant_visible|officer_only`, idempotent on
  client_message_id.
- BL-019C: `GET /api/v1/applications/{id}/transcript` —
  chronological merge of state changes + messages.
- BL-019D-α: `GET /api/v1/applications?state=...&scope_kind=...&scope_id=...&owner_id=...&limit=...&after_id=...`
  — paged officer-facing list.
- BL-016 / INIT-127: Discord OAuth identity via
  `/auth/discord/me` — already wired into the SPA's main.tsx.

Required SPA pieces:
- `services/web/src/features/officer/` (or similar):
  - **ApplicationQueueRoute.tsx** — calls
    `GET /api/v1/applications` with state filter + chapter
    scope; renders a list with "claim" buttons.
  - **ApplicationDetailRoute.tsx** — calls
    `GET /api/v1/applications/{id}`,
    `GET /api/v1/applications/{id}/transcript`,
    `GET /api/v1/applications/{id}/messages`. Renders the
    application + transcript + message thread + decision
    panel. Buttons for `POST /api/v1/applications/{id}/transitions`
    (claim, route, review, approve, deny, etc.) and
    `POST /api/v1/applications/{id}/messages`.
- API client extensions in `services/web/src/api/client.ts`
  with Zod schemas matching the new contracts:
  - `ApplicationListRead`,
    `ApplicationRead`,
    `ApplicationMessageListRead`,
    `ApplicationMessageRead`,
    `ApplicationTranscriptRead` (discriminated union).
- Router wiring in `services/web/src/app/router.tsx` for
  `/applications/queue` and `/applications/{id}`.
- Playwright tests extending `services/web/tests/compat.spec.ts`
  (or a new spec) that exercise the queue + detail flows
  with a seeded officer identity.
- Auth: respects existing Discord OAuth identity from
  `/auth/discord/me`; the SPA distinguishes applicant vs
  officer purely from the auth response + the API's 403
  responses.

Suggested decomposition if BL-019D-β still feels too big:
- **133B-i**: queue page only (list + claim button).
- **133B-ii**: detail page + transcript view (read-only).
- **133B-iii**: message thread + decision actions.

### Other open items

- **BL-010 [open, MEDIUM]** — web form richer inputs (chapter
  selector, multi-page, file upload). Independent of BL-019.
  Touches the public submit form in `services/web/src/main.tsx`
  + the public-intake form fixture in
  `infra/tests/fixtures/web-ui/contract.json`. Requires API
  schema work for `form_definitions.fields` extensions
  (probably needs a new INIT slice to enrich the field types).
- **BL-009 [paused — blocked on BL-019D-β]** — Discord-visible
  side effects on public submit. Officer
  `#applications-review` channel embed + applicant DM with
  link back to in-product page. Will pick up once
  BL-019D-β lands.
- **BL-020 [implicit, deferred]** — applicant DM materialization
  on submit. Per BL-009 user-confirmed direction; depends on
  BL-019D-β + BL-009.

## Patterns + conventions used this session

### Implementation pipeline (per `~/ai/workflows/implementation-pipeline.md`)
- Phase 0 RCA → 2.5 problem-map → 3 proposal → 4 risk gates
  (audit/scope/shortcut/supported-surface) → 5 hookpoints →
  6a contract / 6b separate test-writer / 6c separate code agent →
  7 CodeRabbit.
- Greenfield feature work skips Phase 0; problem-map can fold
  into the proposal.
- Risk gates self-reviewed (LOW × 4 in plans/risk/init-NNN-*.md);
  multi-agent gpt-high gates only when scope/shortcut/audit
  judgment is hard.

### Separated 6b / 6c agents
- Step 6a: human (orchestrator) writes the contract at
  `.tmp/init-NNN/phase6/step6a-contract.md`.
- Step 6b: dispatched as `agents -m gpt-high -p . -f
  .tmp/init-NNN/phase6/step6b-test-writer-prompt.md`. Writes
  ONLY tests + risk annotations. No product code.
- Step 6c: dispatched after 6b completes; writes ONLY product
  code. Cannot edit 6b's tests. May flag
  `CONTRACT_REVISION_NEEDED:<reason>` if a test is wrong.
- Both agents write `STEP6{B,C}_DONE.md` at end with status.
- Orchestrator runs build/rollout/e2e directly — agents
  consistently EXIT=255 at e2e launch (recurring infrastructure
  flake; product code is reliably on disk).

### BACKLOG discipline (per memory `backlog-discipline.md`)
- `plans/BACKLOG.md` is the single index. New residuals/follow-ups
  always land there.
- Pick next work from the top of the highest-priority section.
- When closing: status `[done]` + closing commit SHA + outcome
  paragraph. Don't delete entries; the closed list is the audit
  trail.
- When deferring: `[deferred]` + reason. When superseding:
  `[done — superseded by ...]` + which slice replaced it.

### Test fixture idempotency for `_grant`
INIT-131 surfaced a recurring fixture bug: tests that publish
multiple forms at the same scope grant `application_form.publish`
twice and hit `DuplicateActiveGrantError`. The fix:
```python
try:
    grant_authority(...)
except DuplicateActiveGrantError:
    pass  # idempotent for fixture re-use
```
Reused this pattern in INIT-131 + INIT-133A test files.

## Known recurring issues

### codex EXIT=255 at e2e launch
Documented across INIT-120/121/122/124/125A/127/132/133A. The
codex agent process exits 255 when invoking long-running e2e
shell pipelines, even when the underlying agent work is complete.
Pattern:
1. Verify product code on disk (the agent's writes are durable).
2. Run targeted tests directly.
3. Run e2e directly.

### Port-19090 stale port-forward flake
Test 18-observability fails with
`Unable to listen on port 19090: Listeners failed to create ...
bind: address already in use` when an orphan
`kubectl port-forward` from a previous run hasn't released
port 19090. Fix:
```bash
ps aux | grep "kubectl.*port-forward" | grep -v grep | awk '{print $2}' | xargs -r kill -9
```
Then re-run the e2e. Test 19-web-ui (the meaningful one for
applicant-facing changes) consistently passes.

### Concurrent e2e runs compete for ports
DO NOT start a rerun while the previous run-fullstack.sh is
still going. Even after `RESULT: 18-observability FAIL` and
`SUMMARY: pass=18 fail=1` are logged, the script still has
teardown work and may still hold ports. Verify with:
```bash
ps aux | grep run-fullstack | grep -v grep
```
before starting a rerun. INIT-133A hit this — the first-run
wrapper kept appending to its log while a second-run wrapper
also ran, and they competed.

### compliance_evaluation_worker pre-existing fail
`tests/test_compliance_evaluation_worker.py::test_manual_run_preserves_operator_attribution_on_roster_transition`
has been failing since INIT-127's full API run. Unrelated to
recent INITs. Track separately if this matters; it's been
stable as a single-test failure since then.

## File map (where to find things)

- BACKLOG: `plans/BACKLOG.md`
- Substrate audits: `research/`
- Proposals: `proposals/NN-*.md`
- Risk gates: `plans/risk/init-NNN-{audit,scope,shortcut,supported-surface}.md`
- Audit histories: `plans/audit-history/init-NNN-audit-history.md`
- Per-INIT scratch: `.tmp/init-NNN/phase6/` (gitignored;
  step6a contract + step6b/c agent prompts + STEP6{B,C}_DONE.md)
- Migrations: `migrations/versions/wu-NNN_*.py` —
  current head: `wu_044_application_messages`.
- Worktree: `worktrees/recovery-test-first-audit/`. Don't `cd`
  back to the main worktree without intent.

## Build + e2e cookbook (for the next session)

```bash
# (1) Clean ports if previous session left orphans
ps aux | grep "kubectl.*port-forward" | grep -v grep | awk '{print $2}' | xargs -r kill -9

# (2) Rebuild API image + import to k3d node + rollout
bash infra/scripts/build-channel-image.sh \
  --channel local --app server-manager-api \
  --tag init-113-local --context . \
  --file containers/server-manager/Containerfile.api \
  --no-cache --k3d-import humility-local
kubectl --kubeconfig ~/.kube/humility-local.yaml \
  -n server-manager rollout restart deploy/server-manager-api
kubectl --kubeconfig ~/.kube/humility-local.yaml \
  -n server-manager rollout status deploy/server-manager-api --timeout=240s

# (3) Run full-stack e2e
KUBECONFIG_PATH=~/.kube/humility-local.yaml KEEP_CLUSTER=1 \
  bash infra/tests/e2e/run-fullstack.sh --skip-bringup --keep-cluster
# Expect: SUMMARY: pass=19 fail=0 skip=0
```

For web changes, also rebuild the web image:
```bash
bash infra/scripts/build-channel-image.sh \
  --channel local --app server-manager-web \
  --tag init-118-local --context . \
  --file containers/server-manager/Containerfile.web \
  --no-cache --k3d-import humility-local
kubectl --kubeconfig ~/.kube/humility-local.yaml \
  -n server-manager rollout restart deploy/server-manager-web
```

## Memory state (auto-memory key facts)

- Platform stack locked: Vultr/VKE/Buildkite/FluxCD/Authentik
  (NOT Supabase/Railway).
- Phase 5 in progress; local verification only; no deployments.
- Discord bot already registered (Humility + beta guilds).
- User wants me to drive backlog without asking unnecessary
  prioritization questions; UX questions go to HCI research,
  not user.
- User answers product/strategy/positioning calls; I own
  implementation choices, technical decisions, and pipeline
  human-gates that aren't product tradeoffs.
