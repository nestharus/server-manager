# Risk audit — BUG-9 Alembic auto-apply after gitserver reseed

Inputs:
- Proposal: `proposals/24-bug-9-alembic-autoapply.md`
- RCA: `research/37-bug-9-alembic-autoapply-rca.md`
- Substrate:
  - `infra/scripts/render-gitops-source.py` (existing helpers
    `_copy_gitops_tree` line 81-87, `_tree_digest` line 159-170,
    `_render_source_manifests` line 173-241, `_render_marker`
    line 244-264, `render()` orchestration line 267-281).
  - `infra/scripts/install-flux-for-channel.sh:495-511`
    (`render_local_snapshot`, `reseed_gitserver_only`).
  - `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
    (current stable name `server-manager-alembic-migrate` line 4;
    no `ttlSecondsAfterFinished`; image tag pinned line 30).
  - `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
    (ConfigMap `seed-public-intake-form-payload` line 4;
    Job `seed-public-intake-form` line 257; ConfigMap volume
    reference line 369).
  - `gitops/channels/local/applications/server-manager/kustomization.yaml:14-15`
    (Kustomization includes both files by stable filename).
  - `migrations/versions/` (44 entries including `__pycache__/`).

## Verdict

**Risk level: MEDIUM.** APPROVED WITH REQUIREMENTS — proceed to
implementation, but the migration-tree hash MUST exclude
`__pycache__` and other non-source artifacts; otherwise the
"hash changes only when migrations change" contract is broken on
the very first iteration after Python touches the directory.

The proposal correctly identifies the rerun contract owner (Job
identity), pairs it with TTL cleanup, and stamps both the Alembic
and seed Job names inside the renderer that already owns the
local snapshot boundary. The render-time mutation is sequenced
correctly relative to Flux's source-revision wait (the snapshot
marker re-hashes the mutated tree, so BUG-4's
`wait_for_source_revision` naturally tracks the new content). Job
name lengths fit comfortably under the Kubernetes 63-char DNS
label limit. Hash truncation to 12 hex chars is overwhelmingly
safe at local-channel cardinality. Pattern symmetry across the
two affected Jobs is consistent and the seed payload hash is
correctly scoped to `data["seed.sql"]` only.

The blocker is purely in the Alembic hash-source definition:
`migrations/versions/` contains a `__pycache__/` directory in
practice (currently visible at the head of `ls
migrations/versions/`), and any Python import — including pytest
collection, alembic CLI invocation, or simply
`python -m migrations.env` — mutates `__pycache__/*.pyc` byte
content and timestamps. The proposal text says "including relative
file paths and file bytes" with no exclusion list, and proposes
reusing `_tree_digest` which walks `rglob("*")` unconditionally.
Without an explicit ignore list, the migration hash will drift
across renders without any migration content actually changing,
defeating both Q1 (rerun only on real change) and TG-2 (no
rerun on unchanged migrations).

This is a one-line implementer requirement, not a design defect,
so the verdict is APPROVED WITH REQUIREMENTS rather than a hard
block.

## Findings

### F-1 Hash-source filtering must exclude non-source artifacts — REQUIREMENT

The `migrations/versions/` directory is a Python package and
acquires a `__pycache__/` subdirectory whenever the package is
imported. `ls migrations/versions/` shows `__pycache__` as the
first entry today. The pyc files inside `__pycache__`:

- contain compiled bytecode that depends on the Python version,
- are rewritten on import if the source mtime moves,
- on Linux include an embedded mtime in their header,
- are not under version control and are not part of Alembic's
  migration contract.

The proposal §2 Q2 (lines 47-51) defines the Alembic hash as
"SHA-256 digest of the `migrations/versions/` directory tree,
including relative file paths and file bytes". §3 substrate
(lines 138-141) says the helper "can reuse or generalize the
existing `_tree_digest` behavior, but must read
`REPO_ROOT / 'migrations' / 'versions'` as the Alembic trigger
source." The existing `_tree_digest` at
`infra/scripts/render-gitops-source.py:159-170` walks
`rglob("*")` and only excludes paths in an explicit
`ignored_relative_paths` set; it does not skip `__pycache__/` or
similar directories.

If the implementer reuses `_tree_digest` as-is on
`migrations/versions/`, every subsequent render after pytest /
alembic / mypy / IDE import touches the package will produce a
different `<migration_hash>`, which means:

- TG-2 ("unchanged migrations do not create another Alembic Job")
  will fail intermittently because the rendered Job name will
  drift even when no operator-visible migration changed.
- Local idempotency of `--reseed-gitserver-only` is broken; the
  operator can no longer trust that running the reseed twice in a
  row is a no-op.
- The marker `source_sha` (rendered by `_render_marker` over the
  whole source path) will also drift because the mutated Job name
  embeds the drifting hash, so `wait_for_source_revision` will
  observe a "new" revision on every reseed run.

**Required behavior at implementation time:** the new helper must
include at least these exclusions before computing the digest of
`migrations/versions/`:

- skip any path component named `__pycache__`,
- skip files with extensions `.pyc`, `.pyo`,
- skip dotfiles such as `.DS_Store`, swap files, editor backups
  (`*~`, `.#*`, `*.swp`).

The cleanest expression is to filter on Alembic source semantics:
include only files whose name matches `*.py` and whose path does
not contain a `__pycache__` segment. Anything else under
`migrations/versions/` (a `README.md`, a `helpers/` package) is
either intentional source — in which case `*.py` plus a
restricted set of supporting filenames is fine — or non-source
that should not trigger a rerun.

Either explicitly enumerate the include set, or generalize
`_tree_digest` to take an exclude predicate and call it with one
that drops `__pycache__` segments and compiled-Python file
extensions. Document the exclusion rule next to the helper.

This is the only blocking finding; the rest of the audit is
PASS-with-observations.

### F-2 Hash truncation length is safe for local cardinality — PASS

12 hex chars = 48 bits of entropy. Local-channel cardinality is
small: the migration tree advances at most a few times per
working day per developer, and the seed payload changes on the
order of init-cycles. Birthday-collision space at 2^24
(approximately 16 million) candidates before 50% collision
probability is many orders of magnitude beyond the lifetime
hash count for either Job in any plausible local-channel run.
12 chars also matches the existing `source_sha` truncation
length used by `_render_marker`
(`render-gitops-source.py:170`), so the convention is internally
consistent.

For a remote multi-channel setting we would push back on 48
bits, but the proposal explicitly scopes both content hashes to
local-channel rerun semantics (§3 substrate; §6 anti-scope: no
production service or daemon edits). PASS.

### F-3 Job name length is well under the 63-char DNS label limit — PASS

- `server-manager-alembic-migrate` = 30 chars.
  With `-<12-char-hash>`: 30 + 1 + 12 = 43 chars. Limit 63. OK.
  Pod name (`<job>-<5-char-suffix>`) = 43 + 1 + 5 = 49 chars. OK.
- `seed-public-intake-form` = 23 chars.
  With `-<12-char-hash>`: 23 + 1 + 12 = 36 chars. Limit 63. OK.
  Pod name = 36 + 1 + 5 = 42 chars. OK.

The Job-template pod selector is auto-generated by the Job
controller from `controller-uid`; it does not derive from
`metadata.name`, so the name change does not interact with
selector immutability across reruns. Each new content-addressed
name is a fresh Job object with its own selector. PASS.

### F-4 TTL cleanup interacts with Flux inventory — PASS with observation

`ttlSecondsAfterFinished: 86400` on a content-addressed Job
behaves correctly for the two intended cases:

1. **Source advances within 24h** — new render produces a new
   Job name, old Job is no longer in desired state, Flux prune
   removes the old Job (TTL is a defense in depth here, not the
   primary cleanup). New Job runs. Working as intended.
2. **Source advances after 24h** — TTL has already deleted the
   completed old Job before the new render lands. New render
   produces a new Job name; old name is absent from cluster and
   from desired state. Inventory and prune are both consistent.
   New Job runs. Working as intended.

The same pattern is already in use elsewhere in the local channel
(`gitops/channels/local/observability/loki/bucket-job.yaml` sets
`ttlSecondsAfterFinished: 86400` per RCA "Affected paths"
section), so the convention is precedented and the Flux inventory
behavior is observed in practice.

**Observation (non-blocking):** there is one edge case where TTL
fires before the next reseed and the operator subsequently
reseeds *without* changing migration content. In that window:

- Old completed Job is gone (TTL).
- New render produces the same content-addressed name as before.
- Flux applies it; Kubernetes creates a fresh Job; alembic runs
  again.

For the Alembic Job this is harmless because `alembic upgrade
heads` is idempotent — it observes the database is at heads and
exits immediately. For the seed Job, the seed SQL is database-
level idempotent per RCA §"Existing local patterns". So in both
cases the unexpected re-run is a no-op execution, not a
correctness defect. The cost is one extra Pod cycle per >24h
idle interval. Acceptable for the local channel. Worth a
sentence in the implementation notes so an operator who sees the
re-run does not interpret it as a regression.

### F-5 Pattern symmetry across the two affected Jobs — PASS

The proposal applies a strictly symmetric treatment:

| Aspect | Alembic Job | Seed Job |
|---|---|---|
| Stable checked-in base name | `server-manager-alembic-migrate` | `seed-public-intake-form` |
| Hash source | `migrations/versions/` tree digest | `data["seed.sql"]` of `seed-public-intake-form-payload` ConfigMap |
| Rendered name | `<base>-<12-hex>` | `<base>-<12-hex>` |
| Hash label/annotation | `platform.humility.gg/content-hash: <hash>` on Job + Pod template | same |
| TTL | `ttlSecondsAfterFinished` on Job | `ttlSecondsAfterFinished` on Job |
| ConfigMap identity | n/a | preserved as `seed-public-intake-form-payload` (volume reference unchanged) |
| Kustomization include | unchanged filename | unchanged filename |

The asymmetry that exists is correct: the seed Job carries a
companion ConfigMap whose name must remain stable so the Job's
`spec.template.spec.volumes[0].configMap.name` reference at
`seed-public-intake-form.yaml:369` does not need a content-
addressed redirect. The proposal preserves this. The sequencing
("Flux applies ConfigMap update, then Flux applies new-named Job
which mounts the freshly-updated ConfigMap") is correct because
both objects are in the same Flux Kustomization and ConfigMap
mounts read at Pod start, after the new Job's Pod is scheduled.

Anti-scope (§5) explicitly prevents renaming the manifest files
referenced by the channel Kustomization, so
`gitops/channels/local/applications/server-manager/kustomization.yaml:14-15`
remains the stable file list. Mutation lives inside the rendered
snapshot, not on disk. PASS.

### F-6 Render-time stamping does not race Flux reconcile — PASS

The renderer mutates the snapshot tree at
`.tmp/gitops-source/<channel>/gitops/channels/local/applications/server-manager/`
before the snapshot is written into the in-cluster gitserver and
before any Flux reconcile observes it. Sequence in `render()`
(`render-gitops-source.py:267-281`):

1. `_copy_gitops_tree(out)` — populates the snapshot from
   `gitops/`.
2. `_copy_policy_tree(out)` and `_materialize_cedar_policy_files`
   — touch the policy subtree only.
3. **(new)** structured-YAML mutation of the two manifest files
   inside the snapshot, stamping content-addressed names and
   labels.
4. `_render_source_manifests` — writes the GitRepository and
   Flux Kustomization to `gitops/sources/<channel>/`. Does not
   touch the application subtree.
5. `_render_marker(out, gitops)` — re-hashes the source path
   excluding only the marker itself, and writes the snapshot
   marker ConfigMap.

Critically, step 5 hashes the post-mutation tree, so the marker's
`source_sha` reflects the content-addressed Job names. BUG-4's
`wait_for_source_revision "$SEEDED_REVISION_SHA"`
(`install-flux-for-channel.sh:505`) uses this marker value as
the proof-of-revision artifact. When the migration tree changes,
the rendered Job name changes, the marker changes, and the
reseed wait completes against the new revision — without any
new wiring.

The renderer does not touch the live cluster. Flux reconciles the
gitserver-hosted manifest tree as it always does. There is no
shared mutable state between the renderer and the Flux
controller, so there is no reconcile race. PASS.

The proposal's anti-scope at §5 (lines 224-238) — "Do not make
`reseed_gitserver_only` delete, patch, or reapply application
Jobs" — is consistent with this: the rerun contract lives
entirely in the rendered desired state, not in any imperative
post-reseed mutation.

### F-7 Operator workflow is deterministic and repeatable — PASS (gated on F-1)

Once F-1's exclusion rule is in place, the workflow is:

1. Operator changes a migration file under `migrations/versions/`
   (or seed.sql).
2. Operator runs `bring-up-local-channel.sh --channel local
   --reseed-gitserver-only`.
3. Renderer produces a snapshot whose Job names embed the new
   content hash; marker `source_sha` advances.
4. Reseed pushes snapshot to gitserver; `wait_for_source_revision`
   waits for the new SHA to appear in `GitRepository` artifact.
5. Operator follows the existing BUG-4 instruction to resume /
   reconcile the Flux Kustomization (the script logs the resume
   command at `install-flux-for-channel.sh:509-510`).
6. Flux applies the new-named Job; Kubernetes creates a fresh
   Pod; alembic / seed runs.
7. No `kubectl delete job ...` step is required.

Re-running step 2 without changing migration content (assuming
F-1's `__pycache__` filter is in place) yields:

- bit-identical migration tree digest,
- identical rendered Job names,
- identical marker `source_sha` (modulo other source files which
  are also stable),
- `wait_for_source_revision` is a no-op against the same SHA,
- Flux observes no desired-state change, no new Job created.

This satisfies TG-1 and TG-2 acceptance criteria as written.

For TG-3, modifying `data["seed.sql"]` in
`seed-public-intake-form.yaml` changes the seed hash, produces a
new seed Job name, Flux applies it, the seed runs against the
already-current ConfigMap (which Flux applied in the same
reconcile cycle), and the SQL's existing idempotency reports
"no-op" or "advanced" appropriately per
`seed-public-intake-form.yaml:222-250`. PASS.

## Observations (non-blocking)

1. **Migration scope is `versions/` only.** The proposal
   explicitly hashes `migrations/versions/`. If a future change
   modifies `migrations/env.py`, `migrations/script.py.mako`, or
   `alembic.ini` without touching any file under
   `migrations/versions/`, the rerun trigger will not fire. This
   is a defensible scope (env.py / mako / alembic.ini changes are
   rare and typically accompany an image rebuild that operators
   handle through a different lever) but worth documenting. If
   desired, the helper can take a list of "trigger paths" and
   hash all of them; this is a one-line generalization and does
   not change the verdict.

2. **Image tag is not in the rerun contract.** The Alembic Job's
   image is currently pinned at
   `alembic-migration-job.yaml:30` to
   `k3d-humility-local:5000/local/server-manager-api:init-113-local`.
   The proposal's rerun contract triggers on migration source
   changes, not image-tag changes. If a future image rebuild
   ships new migration code under the same tag without changing
   the migration tree (unlikely but possible), the rerun will
   not fire. Out of scope for BUG-9; image-tag-based rerun is a
   distinct concern handled by `init` cycle rebuilds.

3. **Implementer hygiene: structured YAML mutation must preserve
   document boundaries.** The seed file is a multi-document YAML
   stream (ConfigMap on lines 1-252, then `---` on line 253,
   then Job on lines 254-374). The helper must use
   `yaml.safe_load_all` / `yaml.safe_dump_all` (or load both,
   mutate, and write both back with `---` separators). A naive
   `safe_load` would only see the first document. The proposal
   §3 substrate (lines 142-147) says "loads ... the ConfigMap
   document's `data['seed.sql']` string" — singular — but the
   Job's `metadata.name` mutation in the same file is on the
   second document, so both must round-trip together. Calling
   this out for implementer hygiene.

4. **Validation hook in §3 substrate is correct.** The proposal
   says "Validate that the expected Job and ConfigMap documents
   are present. Fail rendering loudly if they are missing or
   malformed." This is the right defense against a future
   refactor that renames or moves a document and would otherwise
   silently produce a snapshot with a stable Job name. The
   implementer should raise a `ValueError` with an explicit
   filename + expected `kind`/`metadata.name` selector.

5. **`platform.humility.gg/content-hash` label is informational.**
   The actual rerun mechanism is the `metadata.name` change. The
   label or annotation is for operator debugging
   (`kubectl get job -L platform.humility.gg/content-hash`) and
   does not need to be a selector. Adding it to the Pod template
   metadata is harmless and aids traceability when inspecting
   completed Pods. Either label or annotation works; label is
   slightly more useful at the kubectl-grep level.

6. **Diff budget realism.** §6 budget of 90-160 lines across
   three files is consistent with: `_tree_digest` generalization
   or a sibling helper (~15 lines), seed-payload hash helper
   (~10 lines), structured-YAML mutator + multi-document
   round-trip (~30-50 lines), validation (~10 lines), call site
   in `render()` (~5 lines), TTL + content-hash label in each of
   the two manifests (~5-10 lines each). Plausible; no
   surprises.

## Acceptance check (proposed)

When implementation lands, all of the following must hold:

- The migration-tree hash helper in
  `infra/scripts/render-gitops-source.py` excludes
  `__pycache__/` segments and `.pyc` / `.pyo` files (F-1
  requirement). Re-running the renderer twice with no
  source-tree changes produces a bit-identical Alembic Job name.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  carries `ttlSecondsAfterFinished` and a stable readable base
  name; the rendered snapshot stamps the content-addressed
  suffix.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  carries `ttlSecondsAfterFinished` on the Job document, leaves
  the ConfigMap name as `seed-public-intake-form-payload`, and
  leaves the volume reference unchanged.
- The renderer mutates the copied snapshot before
  `_render_marker` so the marker `source_sha` reflects the
  content-addressed names.
- The renderer round-trips the multi-document seed YAML using
  `safe_load_all` + `safe_dump_all` (or equivalent) so both the
  ConfigMap and Job documents are preserved.
- The renderer fails loudly if either expected manifest is
  missing or malformed (validation hook).
- TG-1: a no-op migration file added under `migrations/versions/`
  causes `--reseed-gitserver-only` to produce a Job named
  `server-manager-alembic-migrate-<new_hash>` that reaches
  `Complete`; `alembic_version` advances; no
  `kubectl delete job ...` step is needed.
- TG-2: re-running `--reseed-gitserver-only` without migration
  changes leaves the rendered Alembic Job name identical and
  creates no new Alembic Job in the cluster.
- TG-3: a harmless `seed.sql` payload change produces a new
  `seed-public-intake-form-<new_hash>` Job that reaches
  `Complete`; the seed reports its idempotent outcome.
- `infra/scripts/install-flux-for-channel.sh` `reseed_gitserver_only`
  is unchanged at `:500-511`; no Job deletes, no Job patches, no
  Job re-applies.
- `gitops/channels/local/applications/server-manager/kustomization.yaml:14-15`
  is unchanged.
- No edits to API/daemon/web/repository/service code, migration
  SQL, or application images.
- Diff stays within §6 budget (~90-160 lines across three files).

AUDIT_DONE: plans/risk/bug-9-audit.md
