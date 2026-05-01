# BUG-9 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/24-bug-9-alembic-autoapply.md`
- `research/37-bug-9-alembic-autoapply-rca.md`

## Findings

### 1. Modifies only render-gitops-source.py + the two one-shot Job manifests — PASS

Proposal §3 ("Modified files") declares exactly three files in the change
surface:

- `infra/scripts/render-gitops-source.py` — adds a migrations-tree digest
  helper, a seed-SQL digest helper, and structured-YAML stamping after
  `_copy_gitops_tree(out)` and before `_render_marker(out, gitops)`.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  — adds `ttlSecondsAfterFinished` and optional debug labels; the
  content-addressed suffix is applied to the rendered snapshot, not to the
  checked-in base.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  — adds `ttlSecondsAfterFinished` to the Job document; ConfigMap name
  `seed-public-intake-form-payload` and the Job's volume reference stay
  stable.

This matches the gate criterion "render-gitops-source.py + 2 Job manifests +
(optionally) the local seed Job manifest": the alembic Job is one Job
manifest and the seed-public-intake-form file IS the local seed Job manifest
called out as optional in the gate. Proposal §3 "Unmodified substrate"
explicitly preserves
`gitops/channels/local/applications/server-manager/kustomization.yaml` as a
stable file list, and Anti-scope §5 forbids renaming the manifest files
referenced by the channel Kustomization. Diff budget §6 caps the change at
"three files, roughly 90-160 changed lines."

### 2. No production code changes — PASS

Proposal §3 "Unmodified substrate" states explicitly: "No production API,
daemon, web, repository, service, migration SQL, or application image
changes." Anti-scope §5 reiterates "Do not modify the alembic SQL itself."
Diff budget §6 lists production service or daemon edits and migration SQL
edits under "Not expected." The fix is confined to the render-time
manifest-stamping path and TTL/metadata additions to two Kustomize Job
manifests.

### 3. No Flux reconcile-config changes — PASS

Q3 locks stamping inside `infra/scripts/render-gitops-source.py` precisely
because that path runs before the snapshot lands in the in-cluster
gitserver, removing any need for a post-reseed hook. Proposal §3 explicitly
states `infra/scripts/install-flux-for-channel.sh` "should not delete or
recreate Jobs in `reseed_gitserver_only`. Its existing render, seed,
source-apply, and source-revision wait path is sufficient once rendered Job
names become content-addressed." Anti-scope §5 forbids "Do not change
Flux's GitRepository URL" and "Do not make `reseed_gitserver_only` delete,
patch, or reapply application Jobs." Diff budget §6 excludes "Flux
GitRepository URL or source topology changes." Q4 declines Kustomize
replacements. The rendered `Kustomization` CR's `spec.prune`/`spec.wait`/
`spec.force: true` knobs are untouched.

### 4. No Helm migration — PASS

Anti-scope §5: "Do not switch to Helm." Q4 explicitly rejects Kustomize
replacements as well, opting for direct structured-YAML mutation in the
renderer. The RCA's Candidate E (Helm hook / HelmRelease-managed migration)
was considered and not selected. No HelmRelease, chart, or Helm hook
annotation is added.

### 5. No CronJob — PASS

Anti-scope §5: "Do not add a CronJob runner." The RCA's Candidate F
(CronJob or external runner with run-once semantics) was considered and not
selected. The fix retains `kind: Job` for both the Alembic and seed
manifests; only the `metadata.name` becomes content-addressed and a TTL is
added.

## Conclusion

The proposal stays within the declared three-file change surface
(render-gitops-source.py + the alembic Job manifest + the seed Job/ConfigMap
manifest), touches no production application code, leaves Flux source
topology and reconcile-config knobs alone, does not switch to Helm, and
does not introduce a CronJob. Each gate check passes against a specific
proposal section. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bug-9-scope.md
