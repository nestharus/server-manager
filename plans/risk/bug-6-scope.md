# BUG-6 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/25-bug-6-opal-divergence.md`
- `research/38-bug-6-opal-divergence-rca.md`
- `infra/scripts/install-flux-for-channel.sh`

## Findings

### 1. Only modifies install-flux-for-channel.sh (or adds one helper) — PASS

Proposal §3 "Modified file" lists exactly one file in the change surface:
`infra/scripts/install-flux-for-channel.sh`. The helpers (3-5 small shell
functions for OPAL deployment/pod lookup, rollout wait, and log-signal
waits) are explicitly added inside that same script, not as a new file.
The single call site is in `reseed_gitserver_only` immediately after
`wait_for_source_revision "$SEEDED_REVISION_SHA"` (line 505 in the current
script). Diff budget §6 caps total churn under ~120 lines and explicitly
states "one script-only change" with "no GitOps manifest churn." The
proposal's Q2 lock ("add the bounce inside `reseed_gitserver_only` after
Flux's `GitRepository` confirms the new revision") and the explicit
instruction "Do not add a second operator script" both reinforce the
single-file scope.

### 2. No production code changes — PASS

Proposal §3 "Unmodified substrate" states explicitly: "No production API,
Discord daemon, web, repository, service, migration, OPAL image, OPAL Helm
values, or GitOps manifest changes." Diff budget §6 reiterates "No
production service code." The recovery action operates entirely at the
operator-script layer through `kubectl rollout restart` and log-signal
inspection of the existing `Deployment/auth-system/opal-server` workload —
no application source, image, or chart values are modified.

### 3. No GitOps changes — PASS

Proposal §3 "Unmodified substrate" includes "GitOps manifest changes" in
the unchanged list. The proposal explicitly forbids changes to
`gitops/channels/local/auth/opal-cedar/render-values.yaml`, the rendered
OPAL Server Deployment manifest, and `infra/scripts/render-gitops-source.py`
(the latter is owned by BUG-9). The post-reseed bounce is an imperative
`kubectl` action targeting the already-deployed workload; it does not
mutate any rendered manifest, channel kustomization, source CR, or
Kustomization CR. Q4 confirms `Deployment/auth-system/opal-server` is the
only bounce target — no other GitOps consumer is touched.

### 4. No OPAL image changes — PASS

Proposal §3 "Unmodified substrate" explicitly: "No ... OPAL image, OPAL
Helm values ... changes." Anti-scope §5: "Do not modify OPAL's image or
Git config. The project does not own OPAL's upstream polling
implementation." The recovery is intentionally external to OPAL: the
script restarts the existing container so its fixed clone path
`/opal/regoclone/opal_repo_clone` is recreated from a fresh checkout, per
the RCA's finding that "Restarting OPAL clears the symptom because the
clone lives in the container filesystem." No `OPAL_*` env var, OPAL
Helm value, or OPAL Dockerfile is touched.

### 5. No reseed contract changes (still force-push) — PASS

Anti-scope §5: "Do not redesign the reseed to do fast-forward-only commits.
BUG-4 explicitly locked the reseed contract as a complete local snapshot
force-pushed into the in-cluster gitserver." Proposal §2 Q1 reinforces:
"It keeps BUG-4's source contract intact: the local gitserver remains an
authoritative rendered snapshot that can be replaced by a force-pushed
synthetic commit." The bounce is added strictly *after*
`wait_for_source_revision "$SEEDED_REVISION_SHA"`, so the existing
`seed_git_daemon` flow (`git init --initial-branch=main`, fresh synthetic
commit, `git push --force origin main`) is unchanged. The RCA's
Candidate C (redesign reseed to fast-forward) was considered and rejected.

## Conclusion

The proposal confines the BUG-6 fix to a single shell script
(`infra/scripts/install-flux-for-channel.sh`), adds helpers inline rather
than as a separate file, makes no production code or GitOps manifest
changes, leaves the OPAL image and Helm values untouched, and preserves
BUG-4's force-push reseed contract. Each gate criterion passes against
specific proposal sections. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bug-6-scope.md
