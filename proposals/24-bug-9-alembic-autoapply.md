# Proposal 24 - BUG-9: Alembic auto-apply after gitserver reseed

## 1. Problem statement

The root cause is not that Flux failed to see the new GitRepository artifact.
The source can advance and Flux can report a successful reconcile while the
existing stable-name Kubernetes Job remains complete. The Alembic Job has no
content-addressed identity, no hook/delete lifecycle, and no reseed-time
delete/recreate step. `spec.force: true` only addresses immutable-field update
failures; it does not turn an unchanged completed Job into a newly executed
Job.

The immediate workaround worked because it performed the missing lifecycle
transition manually: remove the completed Job object, then apply the manifest
again so Kubernetes creates a new Job and Pod.

This report intentionally does not select a fix. The next phase should choose
which intervention point owns the rerun contract: Job identity, Flux topology,
the local reseed script, TTL cleanup, Helm lifecycle, or a separate runner.

## 2. Decisions

### Q1. Rerun mechanism

Lock: candidate A, content-addressed Job names.

The migration Job should get a Kubernetes object name derived from the content
that requires a fresh one-shot execution. When the migration tree changes, the
rendered desired state contains a new Job name, so Flux creates a new Job
object and Kubernetes creates a new Pod. This directly addresses the stable
completed-Job root cause without adding a Helm lifecycle, CronJob runner, or
reseed-time imperative delete/reapply step.

The old stable Job name `server-manager-alembic-migrate` is replaced by a
deterministic content-addressed name of the form:

```text
server-manager-alembic-migrate-<12-char-hash>
```

Apply the same object-identity pattern to source-sensitive one-shot seed Jobs
that must rerun when their payload changes.

### Q2. Content hash source

Lock:

- Alembic Job: SHA-256 digest of the `migrations/versions/` directory tree,
  including relative file paths and file bytes, truncated to 12 lowercase hex
  characters.
- Seed Job: SHA-256 digest of the `seed.sql` ConfigMap payload in
  `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`,
  truncated to 12 lowercase hex characters.

Use the migration directory tree instead of only Alembic head id. A tree digest
also changes when an existing migration file is corrected before it has been
accepted as immutable local source, and it avoids relying on parsing revision
metadata from migration modules.

Use the seed SQL payload instead of the full manifest. Labels, TTL, security
context, or unrelated YAML formatting changes should not cause the public
intake seed to rerun; the rerun contract is tied to the SQL data payload.

### Q3. Hash computation and stamping location

Lock: option i, compute and stamp hashes inside
`infra/scripts/render-gitops-source.py`.

`render-gitops-source.py` already owns the local snapshot boundary:

- it copies the `gitops/` tree into `.tmp/gitops-source/<channel>`;
- it materializes generated policy files;
- it renders Flux source manifests;
- it writes the snapshot marker.

The content-addressed Job names must be stamped before the snapshot lands in
the in-cluster gitserver. That makes BUG-4's `--reseed-gitserver-only` path
pick up the new names through its existing `render_local_snapshot` call, with
no post-reseed hook in `reseed_gitserver_only` and no live-cluster Job deletes.

### Q4. How the Job knows its hash

Lock: direct render-time substitution.

After copying `gitops/` into the snapshot, the renderer should load the two
affected YAML files as structured YAML, mutate the copied snapshot documents,
and write them back:

- Set the Alembic Job `metadata.name` to
  `server-manager-alembic-migrate-<migration_hash>`.
- Add a label or annotation carrying the same hash, for example
  `platform.humility.gg/content-hash: <migration_hash>`, on both the Job
  metadata and Pod template metadata.
- Set the seed Job `metadata.name` to
  `seed-public-intake-form-<seed_hash>`.
- Add the same content-hash metadata to the seed Job and Pod template.

Do not introduce Kustomize replacements for this BUG-9 fix. The current local
channel already renders a complete snapshot through Python, and direct
structured YAML mutation keeps the rerun contract in the renderer that owns the
source content. The checked-in source manifests can remain human-readable base
manifests with stable base names; only the rendered gitserver snapshot needs
content-addressed names.

### Q5. Cleanup of stale completed Jobs

Lock: set `ttlSecondsAfterFinished` on the content-addressed Jobs.

Content-addressed names intentionally create new Job objects over time.
Completed historical Jobs should be garbage-collected by Kubernetes after a
short retention window. Use the same TTL field on both Jobs; the implementation
can choose a practical local-retention value such as `86400` seconds unless a
nearer manifest convention already exists.

Do not rely on Flux prune as the primary cleanup mechanism. Prune removes
objects that disappear from the current desired state, but TTL expresses the
Kubernetes Job lifecycle directly and prevents finished one-shot Jobs from
accumulating if an old object remains visible for any interval.

### Q6. Seed Job coverage

Lock: yes, apply the pattern to `seed-public-intake-form` in the same BUG-9
implementation.

The RCA identified the same stable one-shot rerun risk for
`seed-public-intake-form`: the ConfigMap can change while the completed Job
does not execute again. The seed SQL is already written to be database-level
idempotent, so a content-addressed Job name tied to the SQL payload gives the
desired "rerun when source changes" behavior without adding a separate seed
runner.

## 3. Substrate

### Modified files

- `infra/scripts/render-gitops-source.py`
  - Add a helper that hashes a directory tree with deterministic path ordering.
    It can reuse or generalize the existing `_tree_digest` behavior, but must
    read `REPO_ROOT / "migrations" / "versions"` as the Alembic trigger source.
  - Add a helper that loads
    `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
    from the copied snapshot and hashes the ConfigMap document's
    `data["seed.sql"]` string.
  - Add structured YAML mutation for the copied snapshot manifests after
    `_copy_gitops_tree(out)` and before `_render_marker(out, gitops)`.
  - Validate that the expected Job and ConfigMap documents are present. Fail
    rendering loudly if they are missing or malformed.

- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  - Add `ttlSecondsAfterFinished`.
  - Keep the checked-in base name readable. The rendered snapshot is where the
    content-addressed suffix is applied.
  - Add any static labels needed for Flux/Kubernetes selection and debugging.

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  - Add `ttlSecondsAfterFinished` to the Job document.
  - Keep the ConfigMap name stable as `seed-public-intake-form-payload`; only
    the one-shot Job identity is content-addressed.
  - Keep the volume reference to the stable ConfigMap name.

### Unmodified substrate

- `gitops/channels/local/applications/server-manager/kustomization.yaml`
  remains a stable file list. It still includes
  `alembic-migration-job.yaml` and `seed-public-intake-form.yaml`; those files
  are mutated inside the rendered snapshot, not renamed on disk.
- `infra/scripts/install-flux-for-channel.sh` should not delete or recreate
  Jobs in `reseed_gitserver_only`. Its existing render, seed, source-apply, and
  source-revision wait path is sufficient once rendered Job names become
  content-addressed.
- No production API, daemon, web, repository, service, migration SQL, or
  application image changes.

## 4. Test plan

### TG-1: migration change creates and runs a new Alembic Job

Add a no-op migration file under `migrations/versions/` with a new revision and
the previous current head as its down revision. Run the narrow reseed path:

```bash
bash infra/scripts/bring-up-local-channel.sh \
  --channel local \
  --reseed-gitserver-only
```

Resume/reconcile Flux using the existing BUG-4 operator flow if the
Kustomization is suspended. Acceptance:

- the rendered snapshot contains a Job named
  `server-manager-alembic-migrate-<new_hash>`;
- Kubernetes creates a new Alembic Job with that name;
- the Job reaches `Complete`;
- the database `alembic_version` advances to the new no-op migration head;
- no manual `kubectl delete job server-manager-alembic-migrate...` step is
  needed.

### TG-2: unchanged migrations do not create another Alembic Job

Re-run `--reseed-gitserver-only` without changing `migrations/versions/`.

Acceptance:

- the rendered Alembic Job name is identical to the TG-1 rendered name;
- Flux sees identical desired state for the Alembic Job;
- no additional Alembic Job object is created solely because the gitserver was
  reseeded from unchanged migration content.

### TG-3: seed-public-intake-form reruns when seed SQL changes

Make a harmless, reversible local change to the `seed.sql` payload in
`seed-public-intake-form.yaml` that preserves SQL idempotency, then run
`--reseed-gitserver-only` and reconcile Flux.

Acceptance:

- the rendered seed Job name changes to
  `seed-public-intake-form-<new_hash>`;
- Kubernetes creates a new seed Job with that name;
- the Job reaches `Complete`;
- the seed SQL reports its idempotent outcome without operator deletion of the
  prior seed Job.

## 5. Anti-scope

Do not switch to Helm.

Do not add a CronJob runner.

Do not modify the alembic SQL itself.

Do not change Flux's GitRepository URL.

Do not make `reseed_gitserver_only` delete, patch, or reapply application Jobs.

Do not add a compatibility shim preserving the old stable Job names as aliases.

Do not rename the manifest files referenced by the channel Kustomization.

## 6. Diff budget

Expected implementation budget: three files, roughly 90-160 changed lines.

Allowed changes:

- helper functions in `render-gitops-source.py` for migration tree hashing,
  seed SQL payload hashing, and structured YAML stamping;
- TTL and optional hash/debug metadata additions in the Alembic Job manifest;
- TTL and optional hash/debug metadata additions in the seed Job manifest.

Not expected:

- production service or daemon edits;
- migration SQL edits;
- Flux GitRepository URL or source topology changes;
- new scripts unless implementation proves `render-gitops-source.py` cannot
  safely own the stamping step;
- broad GitOps directory rewiring.
