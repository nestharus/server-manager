# BUG-9 — Shortcut risk gate (Alembic auto-apply after gitserver reseed)

**Verdict:** LOW

Source: `proposals/24-bug-9-alembic-autoapply.md`,
`research/37-bug-9-alembic-autoapply-rca.md`,
`infra/scripts/render-gitops-source.py`,
`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`,
`gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`.

## C1 — Real content-addressed naming, not stable-name + force-delete

**Pass.**

Q1 (proposal lines 23-42) locks candidate A and is explicit about what
"content-addressed" means here:

> The migration Job should get a Kubernetes object name derived from the
> content that requires a fresh one-shot execution. When the migration tree
> changes, the rendered desired state contains a new Job name, so Flux
> creates a new Job object and Kubernetes creates a new Pod.

The rendered name shape is concrete:

> `server-manager-alembic-migrate-<12-char-hash>`

Q2 (lines 44-63) names the bytes that go into the hash for both Jobs:

- Alembic Job: SHA-256 over `migrations/versions/` directory tree (relative
  paths + file bytes), truncated to 12 lowercase hex chars.
- Seed Job: SHA-256 over the `seed.sql` ConfigMap payload at
  `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`,
  same truncation.

Q4 (lines 82-103) commits to render-time YAML mutation:

> After copying `gitops/` into the snapshot, the renderer should load the
> two affected YAML files as structured YAML, mutate the copied snapshot
> documents, and write them back:
>
> - Set the Alembic Job `metadata.name` to
>   `server-manager-alembic-migrate-<migration_hash>`.
> - Add a label or annotation carrying the same hash …
> - Set the seed Job `metadata.name` to
>   `seed-public-intake-form-<seed_hash>`.
> - Add the same content-hash metadata to the seed Job and Pod template.

This is the actual identity flip — the rendered snapshot Job has a new
`metadata.name`, which is exactly what makes Flux see a new desired object
and Kubernetes create a new Job/Pod (the only reliable trigger described in
RCA section "Why one-shot Jobs are not re-run", lines 80-101).

The shortcut variant — keep the stable name and have `reseed_gitserver_only`
delete + reapply the Job — is explicitly forbidden by anti-scope:

> Do not make `reseed_gitserver_only` delete, patch, or reapply application
> Jobs.
> Do not add a compatibility shim preserving the old stable Job names as
> aliases.

Substrate (lines 162-172) reinforces the boundary:

> `infra/scripts/install-flux-for-channel.sh` should not delete or recreate
> Jobs in `reseed_gitserver_only`. Its existing render, seed, source-apply,
> and source-revision wait path is sufficient once rendered Job names become
> content-addressed.

The choice of hashing the migration **directory tree** rather than the
Alembic head id is deliberate (Q2 lines 56-60: "A tree digest also changes
when an existing migration file is corrected before it has been accepted as
immutable local source, and it avoids relying on parsing revision metadata
from migration modules"). That avoids a subtler shortcut: parse `down_revision`
chains from migration modules to derive a head id, which would silently miss
in-place edits to a not-yet-immutable migration file during local iteration.

The hash source choice for the seed Job is also tight (Q2 lines 61-63:
"Use the seed SQL payload instead of the full manifest. Labels, TTL, security
context, or unrelated YAML formatting changes should not cause the public
intake seed to rerun"). That blocks the alternate shortcut of hashing the
whole document, which would couple seed reruns to cosmetic YAML edits.

Cross-checked against the renderer source: `_tree_digest` already exists at
`infra/scripts/render-gitops-source.py:159`, `_copy_gitops_tree` at `:81`,
and the render() ordering is `_copy_gitops_tree(out)` (line 277) →
`_render_marker(out, gitops)` (line 281). The proposal's stamping insertion
point — between `_copy_gitops_tree(out)` and `_render_marker(out, gitops)`,
mutating the **copied** snapshot — is consistent with that flow and keeps
the checked-in base manifests human-readable while the rendered snapshot
carries the content-addressed identity.

## C2 — TTL-based cleanup actually configured (not just promised)

**Pass.**

Q5 (proposal lines 106-118) is a lock, not a deferral:

> Lock: set `ttlSecondsAfterFinished` on the content-addressed Jobs.
>
> Content-addressed names intentionally create new Job objects over time.
> Completed historical Jobs should be garbage-collected by Kubernetes after
> a short retention window. Use the same TTL field on both Jobs; the
> implementation can choose a practical local-retention value such as
> `86400` seconds unless a nearer manifest convention already exists.

Substrate translates that into per-file edits:

- Alembic Job (lines 150-153): "Add `ttlSecondsAfterFinished`."
- Seed Job (lines 155-159): "Add `ttlSecondsAfterFinished` to the Job
  document."

Verified that today neither manifest sets the field —
`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:1-62`
has no `ttlSecondsAfterFinished` (only `backoffLimit: 6` and pod template),
and `seed-public-intake-form.yaml:254-284` likewise has no TTL on the seed
Job document. So the substrate change is a real addition rather than a
restatement of existing config.

The 86400-second default is consistent with an existing project precedent:
RCA "Affected paths" section (lines 292-294) records that
`gitops/channels/local/observability/loki/bucket-job.yaml` already uses
`ttlSecondsAfterFinished: 86400` for a stable-name bootstrap Job, so the
chosen value isn't invented — it matches the local-retention convention
already in the repo.

The proposal also blocks the alternate shortcut of relying on Flux prune
for cleanup (Q5 lines 117-118):

> Do not rely on Flux prune as the primary cleanup mechanism. Prune removes
> objects that disappear from the current desired state, but TTL expresses
> the Kubernetes Job lifecycle directly and prevents finished one-shot Jobs
> from accumulating if an old object remains visible for any interval.

That matches the RCA's framing of TTL as a Kubernetes-native lifecycle
mechanism (lines 102-107) rather than a side effect of GitOps reconciliation.
With content-addressed names creating a new Job per migration tree change,
a missing TTL would let completed Jobs accumulate indefinitely; the proposal
addresses that head-on rather than punting to "we'll add TTL later."

## C3 — TG-1 actually adds a no-op migration and verifies the Job re-runs

**Pass.**

TG-1 (proposal lines 176-196) is structured as:

1. **Trigger:** add a no-op migration file under `migrations/versions/` with
   a new revision and the previous current head as its down revision.
2. **Action:** `bash infra/scripts/bring-up-local-channel.sh --channel local
   --reseed-gitserver-only`, then resume/reconcile Flux via the existing
   BUG-4 operator flow if the Kustomization is suspended.
3. **Acceptance:**
   - the rendered snapshot contains a Job named
     `server-manager-alembic-migrate-<new_hash>`;
   - Kubernetes creates a new Alembic Job with that name;
   - the Job reaches `Complete`;
   - the database `alembic_version` advances to the new no-op migration head;
   - no manual `kubectl delete job server-manager-alembic-migrate...` step
     is needed.

That hits every link of the rerun chain, not just the leaf:

- *Rendered name change* validates that `render-gitops-source.py` actually
  re-hashes the migration tree and stamps a different `metadata.name` —
  i.e., the content-hash trigger is wired to the right bytes.
- *Kubernetes Job creation* validates that Flux observes the new desired
  name and creates a new object — the actual GitOps-side rerun contract.
- *Job reaches Complete* validates the new Pod actually executes (not just
  that the object materializes).
- *`alembic_version` advances* validates end-to-end migration correctness,
  not just Job lifecycle — this is the database-side proof that the rerun
  is functionally equivalent to the manual `kubectl delete + apply`
  workaround that worked in the bug report (RCA lines 18-19).
- *No manual delete step needed* is the negative assertion against the
  operator workflow that exposed the bug; if the test passed but the
  acceptance criterion let an implicit `kubectl delete` slip in, it would
  hide a regression to the manual-workaround behavior.

The "no-op migration" framing is also right: it isolates the rerun contract
from any database-side data hazard. A real migration could pass even if the
Job had previously been re-run by some other mechanism, but a no-op
migration only advances `alembic_version` if the Job actually executed
once after the migration was added.

The reseed entry point matches the RCA's reproduction path (research
lines 49-60: BUG-4's `reseed_gitserver_only` does **not** call
`request_kustomization_reconciliation` and does **not** delete/recreate
Jobs), so TG-1 hits the exact bug surface, not an adjacent path that already
worked.

## C4 — TG-2 actually verifies a no-change reseed produces no new Job

**Pass.**

TG-2 (proposal lines 198-207) is structured as:

1. **Trigger:** re-run `--reseed-gitserver-only` without changing
   `migrations/versions/`.
2. **Acceptance:**
   - the rendered Alembic Job name is identical to the TG-1 rendered name;
   - Flux sees identical desired state for the Alembic Job;
   - no additional Alembic Job object is created solely because the
     gitserver was reseeded from unchanged migration content.

That checks the *negative* leg of the contract — content-addressed Jobs must
not over-trigger. Without TG-2, a shortcut implementation that hashed the
*reseed timestamp* or the entire snapshot bytes (which would change every
reseed even with unchanged migration content) would silently pass TG-1 and
turn every local reseed into a fresh migration Pod, which is exactly what
the seed-payload hashing decision in Q2 was trying to avoid.

The three acceptance leaves cover the chain:

- *Identical rendered name* validates the hash is over migration content
  only, not over rendering metadata.
- *Identical Flux desired state* is the GitOps-layer sanity check — Flux
  shouldn't even attempt to create a new Job because the desired state
  matches.
- *No additional Job object created* is the Kubernetes-layer sanity check —
  the completed Job from TG-1 stays as the in-cluster object, no second
  Pod runs.

Pairing TG-1 and TG-2 around the same migration-tree boundary is the right
shape: TG-1 proves the trigger fires when it should; TG-2 proves it does
not fire when it shouldn't. The two together pin both directions of the
content-addressed contract.

TG-3 (lines 209-222) extends the same shape to the seed Job (a "make a
harmless, reversible local change to the `seed.sql` payload" trigger with
acceptance asserting the rendered seed Job name changes,
`seed-public-intake-form-<new_hash>` materializes, the Job reaches
`Complete`, and "the seed SQL reports its idempotent outcome without
operator deletion of the prior seed Job"). That covers Q6's "yes, apply the
pattern to seed-public-intake-form in the same BUG-9 implementation"
locked decision (lines 122-130), so the seed-Job rerun contract is also
gated by a real test, not just promised behavior.

## C5 — No "TODO" stubs

**Pass.**

`grep -n 'TODO|TBD|FIXME|XXX' proposals/24-bug-9-alembic-autoapply.md` finds
no matches. Every commitment in the proposal is named with a concrete file,
function, or manifest field; none of the substrate edits are deferred to a
follow-up.

Substrate (lines 134-160) is enumerated per file:

- `infra/scripts/render-gitops-source.py` — four named additions:
  - directory-tree hashing helper (must read `REPO_ROOT / "migrations" /
    "versions"`; can reuse/generalize existing `_tree_digest` at
    `:159`);
  - seed-payload hashing helper (loads
    `seed-public-intake-form.yaml` from the copied snapshot and hashes the
    ConfigMap document's `data["seed.sql"]` string);
  - structured YAML mutation step inserted between `_copy_gitops_tree(out)`
    (line 277 of the script today) and `_render_marker(out, gitops)`
    (line 281);
  - validation that the expected Job and ConfigMap documents are present,
    with loud rendering failure if missing/malformed.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  — TTL field, base-name preservation, optional debug/labels.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  — TTL on the Job document, ConfigMap name held stable as
  `seed-public-intake-form-payload`, volume reference unchanged.

The "Unmodified substrate" section (lines 162-172) is *bounding*, not
*deferring* — it explicitly names what stays unchanged and why
(`kustomization.yaml` keeps its file list because mutation happens inside
the snapshot, not via on-disk renames; `install-flux-for-channel.sh` keeps
`reseed_gitserver_only` as render+seed+apply+wait without Job manipulation).

Anti-scope (lines 224-238) closes the perimeter without parking work: it
rules out switching to Helm, adding a CronJob runner, modifying SQL,
changing Flux's GitRepository URL, making `reseed_gitserver_only` mutate
Jobs, adding compatibility shims, and renaming manifest files. None of
those are deferred — they are decisions to *not do them at all*, which is
the right framing for a tightly scoped fix.

Diff budget (lines 240-258) is "three files, roughly 90-160 changed lines"
with a precise allowed-changes list (helpers in the renderer; TTL +
optional metadata in two manifests). A budget that intended to defer
seed-Job work would have separated the budget into "alembic now, seed
later" or pointed to a follow-up file; this one bundles both Jobs in the
same scope.

## Findings worth carrying into implementation

Not blockers — verdict is LOW — but the implementation phase should
preserve:

1. **Hash inputs must be byte-stable, not order-stable in arbitrary ways.**
   The Q2 spec is "SHA-256 digest of the `migrations/versions/` directory
   tree, including relative file paths and file bytes." The implementer
   should sort the directory entries by relative path before hashing, mix
   the path bytes into the digest before each file's bytes, and use a
   canonical separator (e.g., NUL) so that a path collision like
   `a/b` + `c` vs `a` + `b/c` cannot collide. The existing `_tree_digest`
   helper at `render-gitops-source.py:159` is the right model to reuse,
   but if it ignores any files (the existing call at line 249 passes
   `{f"generated/{MARKER_NAME}"}` as `ignored_relative_paths`), the
   migration-tree caller should pass `None` so every migration file
   contributes — particularly important if a future generated migration
   helper ever lands under `migrations/versions/`.

2. **Ignore `__pycache__` and `*.pyc` under `migrations/versions/` when
   hashing, or the digest changes on every Python import.** The substrate
   says "must read `REPO_ROOT / "migrations" / "versions"` as the Alembic
   trigger source" but does not call out compiled-Python artifacts. If
   the renderer runs after the migrations have been imported once
   (e.g., by a previous test run in the same checkout), `__pycache__/*.pyc`
   files appear under `migrations/versions/__pycache__/` and would change
   the tree digest non-deterministically. The implementer should filter
   on suffix (`.py` only) or exclude `__pycache__/` directories explicitly,
   then exercise the no-change reseed (TG-2) **after** a `pytest` run to
   verify the digest is stable across that boundary.

3. **The label/annotation hash on the Pod template metadata must match
   the Job-level hash exactly.** Q4 says "Add a label or annotation
   carrying the same hash, for example
   `platform.humility.gg/content-hash: <migration_hash>`, on both the Job
   metadata and Pod template metadata." The Pod template hash matters
   because it's the field Kubernetes inspects when deciding whether a Job
   can be patched in place (immutable pod template fields). Stamping the
   same hash on the pod template guarantees that even if a future change
   reuses an existing Job name (e.g., a hash collision or a manual
   rerender), Flux's `spec.force: true` will recreate the Job rather than
   silently no-op. Use `platform.humility.gg/content-hash` consistently
   across both the Job and Pod-template `metadata.labels` (or `annotations`,
   but pick one and stay consistent with the existing manifest's
   `app.kubernetes.io/...` label scheme at lines 6-9 / 14-17 of
   `alembic-migration-job.yaml`).

4. **`metadata.name` length budget — 63 chars total.** The base name
   `server-manager-alembic-migrate` is 30 characters, plus `-` plus the
   12-char hash = 43 characters, well under Kubernetes' 63-character DNS
   subdomain limit. The base name `seed-public-intake-form` is 23
   characters, plus `-` plus 12 = 36. Both fit. But the implementer
   should sanity-check at render time and fail loudly if any future base
   name + hash exceeds 63 chars rather than silently truncating.

5. **The renderer's failure mode for "expected Job/ConfigMap document not
   found" must be loud and actionable.** Substrate line 147 says
   "Validate that the expected Job and ConfigMap documents are present.
   Fail rendering loudly if they are missing or malformed." The error
   should name which file and which expected `metadata.name` (or kind)
   was missing, not just "validation failed." A silent skip would let a
   future refactor remove or rename one of these manifests and the
   stamping would no-op without anyone noticing — until reseed stopped
   triggering reruns again.

6. **Watch the BUG-4 operator-flow handoff in TG-1.** The TG-1 wording
   "Resume/reconcile Flux using the existing BUG-4 operator flow if the
   Kustomization is suspended" matches the RCA's documented behavior
   (research lines 49-60: `reseed_gitserver_only` does not call
   `request_kustomization_reconciliation` and does not wait for the Flux
   `Kustomization`). The implementer should record the exact operator
   step taken (e.g., `flux reconcile kustomization ... --with-source` or
   manual `kubectl annotate` + wait), so TG-1's "the Job reaches Complete"
   timing is measured from a defined point. Otherwise a slow Flux
   reconcile interval could cause TG-1 to flake under "is the Job there
   yet" assertions.

7. **TG-2's "no additional Job object" assertion should be measured by
   listing Jobs by base-name prefix, not by a single name lookup.**
   Asserting only "the named Job from TG-1 still exists" would pass even
   if TG-2 caused a *second* Job to be created with a slightly different
   hash (e.g., due to the `__pycache__` issue in finding 2). The
   assertion should be `kubectl get jobs -l
   app.kubernetes.io/component=migrations -n server-manager -o name | wc
   -l` equals 1 (or whatever count TG-1 left), so a spurious extra Job
   from a hash drift is caught.

8. **TG-3 (seed Job) acceptance "the seed SQL reports its idempotent
   outcome" needs a concrete observable.** The proposal language is
   correct intent but does not name the assertion. The seed SQL has
   database-level idempotency that surfaces as a `seed_outcome` value in
   a SELECT (visible at `seed-public-intake-form.yaml:250` —
   `END AS seed_outcome;`). The TG-3 implementer should query that
   outcome from the Pod logs or via a `psql` query post-Complete to
   actually observe idempotent re-execution, rather than relying on
   "Complete" status alone (which would also be reached by a no-op or
   silent-error path).

## Verdict

LOW. No shortcuts. The proposal:

- Locks Q1 to true content-addressed Job names (`server-manager-alembic-
  migrate-<12-char-hash>` and `seed-public-intake-form-<12-char-hash>`),
  with the hash bytes tied to the actual rerun trigger source for each
  Job (migration tree for Alembic, `seed.sql` payload for seed), stamped
  at render time inside the existing `render-gitops-source.py` snapshot
  boundary — not a stable name with a force-delete or imperative
  delete-and-reapply step.
- Configures `ttlSecondsAfterFinished` on both content-addressed Jobs in
  the substrate edit list, with a concrete default value (`86400`) that
  matches the existing repo convention from
  `gitops/channels/local/observability/loki/bucket-job.yaml`, and
  explicitly rejects relying on Flux prune as a substitute.
- TG-1 adds a real no-op migration to `migrations/versions/`, runs the
  same `--reseed-gitserver-only` path that exposed the bug, and asserts
  the full chain: rendered name change → new Job object → Complete →
  `alembic_version` advances → no manual `kubectl delete` needed.
- TG-2 re-runs `--reseed-gitserver-only` without changing
  `migrations/versions/` and asserts identical rendered name, identical
  desired state, and no additional Job object — the negative leg of the
  contract that would catch a "hash includes timestamp" or
  "hash includes snapshot bytes" shortcut.
- Lands all substrate edits (renderer helpers + TTL on both manifests +
  YAML mutation step) in one bundle across three named files, with no
  TODO/TBD/FIXME stubs, an anti-scope that bounds (not parks) the work,
  and a 90-160 line diff budget that is consistent with everything
  shipping together.

SHORTCUT_DONE: plans/risk/bug-9-shortcut.md
