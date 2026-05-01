# BUG-10 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/23-bug-10-transcript-reactivity.md`
- `research/36-bug-10-transcript-reactivity-rca.md`
- `services/web/src/features/officer/ApplicationDetailRoute.tsx`

## Findings

### 1. Modifies only ApplicationDetailRoute.tsx and the 5 children per proposal §3 — PASS

Proposal §3 lists three modified source files plus one new test file:

- `services/web/src/features/officer/ApplicationDetailRoute.tsx`
- `services/web/src/features/officer/ApplicationMessageComposer.tsx`
- `services/web/src/features/officer/ApplicationTransitionActions.tsx`
- `services/web/tests/ApplicationDetailRoute.spec.tsx` (new)

The five affected children resolve to those three source files because three
of the five children are defined inside `ApplicationDetailRoute.tsx` itself:

- `ApplicationMetadataPanel` — `ApplicationDetailRoute.tsx:110`
- `ApplicationResponsesPanel` — `ApplicationDetailRoute.tsx:144`
- `ApplicationTranscriptList` — `ApplicationDetailRoute.tsx:167`
- `ApplicationMessageComposer` — separate file
- `ApplicationTransitionActions` — separate file

No additional files outside this set are pulled into the proposal's modified
list or implementation shape (§3) or diff budget (§6).

### 2. No compat shim changes — PASS

Anti-scope §5 explicitly forbids modifications to
`services/web/src/solid-compat/solid.ts`. Diff budget §6 reiterates the same
exclusion. RCA §6 confirms `For`/`Show` come from the shim as direct aliases
and the shim is not the root cause; the fix lives in the call site.

### 3. No API/bridge changes — PASS

Anti-scope §5 forbids changes to the API, transcripts service, bridge
endpoints, transcript serialization, message append payloads, transition
contracts, and authorization behavior. Diff budget §6 also excludes API
client changes and service/repository changes. The fix is purely a
client-side reactivity refactor: replace stale destructure in the parent
`Show` with accessor props and switch child read sites to call those
accessors.

### 4. No new dependencies — PASS

Diff budget §6 explicitly excludes "new frontend dependencies." The proposal
fix uses primitives already imported (`Show`, `For`, `createSignal`) from
the existing Solid runtime. No package additions are required.

### 5. No version bumps — PASS

No package upgrades, no Solid version change, and no shim bump are
contemplated. RCA §6 deliberately leaves the Solid 2 beta runtime in place
and works within its unkeyed `Show` semantics. Anti-scope §5 forbids
"alternate component paths" or feature flags that would imply a parallel
version.

### 6. Test additions are scoped to detail route reactivity — PASS

New test: `services/web/tests/ApplicationDetailRoute.spec.tsx` (proposal
§3, §4 TG-2). The spec mocks `/api/me`, the application detail endpoint,
and two transcript responses, then asserts the already-mounted transcript
DOM updates after `setTranscript(...)` is triggered through a user-visible
action (message append or refresh). It does not introduce test-only exports
or expose `setTranscript` (proposal §2 Q3).

The TG-1 e2e re-run uses the existing `infra/tests/e2e/tests/19-web-ui.sh`
without modification.

## Conclusion

The proposal stays within the declared modification surface (3 source files
+ 1 new test file), respects every anti-scope clause (compat shim, API,
bridge, deps, versions, layout, broad rewrites), and limits new tests to
detail-route reactivity. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bug-10-scope.md
