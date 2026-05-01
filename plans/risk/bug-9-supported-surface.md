# BUG-9 — Supported-surface risk gate

**Verdict:** LOW

BUG-9 (a stable-name `batch/v1` Job
`server-manager-alembic-migrate` reaches `status.succeeded=1` and
never re-executes after a `--reseed-gitserver-only` advances the
in-cluster gitserver, because Flux's `spec.force: true` only repairs
immutable-field patch failures and the rendered Pod template is
effectively unchanged across migrations — RCA §"Why one-shot Jobs are
not re-run") is repaired by stamping a content-addressed suffix onto
the rendered snapshot's Job `metadata.name` (proposal §2 Q1, Q4):
`server-manager-alembic-migrate-<sha256(migrations/versions tree)[:12]>`
for the Alembic Job and `seed-public-intake-form-<sha256(seed.sql)[:12]>`
for the public-intake seed Job. The hash is computed and substituted
inside `infra/scripts/render-gitops-source.py` after
`_copy_gitops_tree(out)` and before `_render_marker(out, gitops)`
(proposal §2 Q3, §3); the checked-in base manifests retain their
human-readable stable names and only gain a `ttlSecondsAfterFinished`
field plus an optional `platform.humility.gg/content-hash` label
(proposal §2 Q5, §3). No public API, no env var, no Alembic SQL, no
Pomerium/Authentik/OPAL resource, and no container `command` array is
touched (proposal §3 "Unmodified substrate", §5 anti-scope).

## Surfaces touched

### 1. Public API — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| HTTP/gRPC routes exposed by `services/api` | as today | unchanged — proposal §3 "Unmodified substrate": "No production API, daemon, web, repository, service, migration SQL, or application image changes" | none |
| Bridge endpoints consumed by `services/web` | as today | unchanged — out of the modified-files list (proposal §3 limits edits to one renderer script and two GitOps Job manifests) | none |
| `kubectl`/Job-name selectors used by operators | the failing operator workflow used `kubectl delete job server-manager-alembic-migrate` (RCA §"Symptom + state") | the rendered Job carries a content-addressed name; the *checked-in* base manifest retains the stable `server-manager-alembic-migrate` for readability (proposal §3, "Keep the checked-in base name readable. The rendered snapshot is where the content-addressed suffix is applied") — selectors that target by Job name change behavior, but operator workflow per proposal §5 anti-scope no longer needs `kubectl delete job` (the rerun is automatic) | low — selectors based on `app.kubernetes.io/name=server-manager-api` and `app.kubernetes.io/component=migrations` labels remain valid; only literal `metadata.name` selectors would need to use the content-hash label or a name prefix |

Risk on §1: **none** for any external API surface; **low** for
operator selectors that target the Alembic Job by literal
`metadata.name` (the manual `kubectl delete job
server-manager-alembic-migrate` workaround stops applying, but
proposal §1 explicitly retires that workaround as the deliverable).
Gate criterion 1 (no public API change) holds.

### 2. Environment variables — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Job env block (`DATABASE_URL` from `server-manager-postgres-url` secret, see `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:39-44`) | as today | unchanged — proposal §3 modifies metadata (`name`, labels, `ttlSecondsAfterFinished`) only; the container `env`, `command`, `image`, `securityContext`, and `resources` blocks are not in the diff budget (§6: "TTL and optional hash/debug metadata additions") | none |
| Renderer env (`infra/scripts/render-gitops-source.py`) | already reads `REPO_ROOT`, channel name, etc. | unchanged — the new helpers read the migrations directory tree and the seed YAML from disk via existing path conventions; no `os.environ` access is added (proposal §3 modified-files list) | none |
| Reseed entry point (`infra/scripts/install-flux-for-channel.sh`) | as today | unchanged — proposal §3 "Unmodified substrate": "`infra/scripts/install-flux-for-channel.sh` should not delete or recreate Jobs in `reseed_gitserver_only`" | none |

Risk on §2: **none** — gate criterion 2 (no env vars) holds.
Proposal §6 budget excludes daemon edits and runtime env reads; the
diff is purely render-time YAML manipulation plus a TTL field on two
Job manifests.

### 3. DB migrations — none beyond what Alembic already provides

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `migrations/versions/` files | current head per repo state | unchanged by this fix — proposal §5 anti-scope: "Do not modify the alembic SQL itself"; proposal §3 modified-files list contains no `migrations/` entries | none |
| Test artifact (TG-1: "Add a no-op migration file") | n/a | a no-op migration is added *only* in the test plan to exercise the rerun contract; this is test substrate, not part of the production fix (proposal §4 TG-1) | none |
| Alembic head advancement contract | `alembic_version` advances when migrations execute | unchanged — the fix changes *when the migration Job re-executes*, not the SQL Alembic runs; the Job continues to invoke `alembic -c /app/alembic.ini upgrade heads` (Job manifest line 33-38, retained per proposal §3 "Unmodified substrate") | none |
| `seed-public-intake-form` SQL payload | database-level idempotent (RCA §"Existing local patterns") | unchanged — the ConfigMap `data["seed.sql"]` content is *read* to compute the hash (proposal §2 Q2), not modified; SQL idempotency continues to gate "harmless" reruns (proposal §4 TG-3 acceptance) | none |

Risk on §3: **none** — gate criterion 3 (no DB migrations beyond
what Alembic already provides) holds. The fix changes Job *identity*
to trigger the existing `alembic upgrade heads` invocation when the
migration tree advances; it does not author, edit, or skip any
migration.

### 4. Pomerium / Authentik / OPAL — none

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `gitops/channels/local/auth/pomerium/**` | as today | unchanged — proposal §3 modifies only `infra/scripts/render-gitops-source.py` plus two manifests under `gitops/channels/local/applications/server-manager/`; no auth tree path is in the diff budget | none |
| `gitops/channels/local/auth/authentik/**` (blueprints, OAuth sources, property mappings) | as today (recent BUG-8 fixes restored claim chain) | unchanged — Authentik objects, Discord OAuth source, claim-chain property mappings are out of the modified-files list | none |
| OPAL policy bundle / OPA decision endpoints | as today | unchanged — no policy file edits; proposal §5 anti-scope explicitly bars Helm/CronJob/runner/topology rewrites that would touch policy | none |
| Pomerium route allowlist / claim header forwarding | as today | unchanged — the failing reproduction in the RCA was an in-cluster Job lifecycle issue, not an auth-path issue; `/api/web/...` traffic does not flow through the Alembic Job at all | none |

Risk on §4: **none** — gate criterion 4 (no Pomerium/Authentik/OPAL
changes) holds. The renderer touches only the server-manager
application slice of the rendered snapshot, identified by file path
in proposal §3 ("structured YAML mutation for the copied snapshot
manifests").

### 5. Job container args — unchanged

The user-supplied gate text reads "the Job's container args remain
`alembic upgrade head`". The current manifest at
`gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:33-38`
actually invokes `alembic -c /app/alembic.ini upgrade heads`
(plural, four flag tokens). This pre-existing wording is *not*
changed by the fix — flagging the textual difference for traceability
only.

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `containers[0].command` array (`alembic`, `-c`, `/app/alembic.ini`, `upgrade`, `heads`) | as today, lines 33-38 | unchanged — proposal §3 "Unmodified substrate": "No production API, daemon, web, repository, service, migration SQL, or application image changes"; §6 diff budget restricts manifest edits to "TTL and optional hash/debug metadata additions" | none |
| `containers[0].args` | not used (command-only invocation) | unchanged — neither proposal §3 nor §6 introduces an `args` field | none |
| `containers[0].image` | static tag `init-113-local` (RCA §"Symptom + state", "The image tag is currently static") | unchanged — image-tag rewriting is explicitly *not* the chosen rerun mechanism (proposal §2 Q1 selects content-addressed Job names; image-tag bumping is a discarded alternative) | none |
| `imagePullPolicy`, `workingDir`, `securityContext`, `resources`, `env` | as today | unchanged — outside the metadata block that proposal §3 mutates | none |
| `restartPolicy`, `backoffLimit`, `template.spec` immutable fields | as today | unchanged — same reason | none |

Risk on §5: **none** — gate criterion 5 (Job's container args
remain unchanged with no signature change) holds. The fix is
metadata-only on the Job document; the Pod template, including
`command`, `image`, `env`, and `securityContext`, is byte-identical
across the rerun.

### 6. Run-once contract — preserved by content-addressed names + TTL

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Each migration tree advance triggers exactly one new Alembic Pod | broken: "the database can remain at an older Alembic head even though the reseeded worktree contains newer files under `migrations/versions/`" (RCA §"Symptom + state") | restored: a new tree digest yields a new `metadata.name` (`server-manager-alembic-migrate-<new_hash>`), Flux applies the new Job document, Kubernetes creates a new Job + Pod (proposal §2 Q1, §4 TG-1 acceptance) | none — directly satisfies the gate |
| Unchanged migration tree does *not* spawn a redundant Pod | one-shot Job stays complete (the bug's silent-success failure mode) | rendered Job name is identical, Flux sees identical desired state, no new Job object is created (proposal §4 TG-2 acceptance: "Flux sees identical desired state for the Alembic Job; no additional Alembic Job object is created") | none |
| Old completed Job objects do not accumulate | `ttlSecondsAfterFinished` is unset; the TTL controller does not clean Jobs (RCA §"Why one-shot Jobs are not re-run", citing the Kubernetes TTL docs) | both Jobs gain `ttlSecondsAfterFinished` (proposal §2 Q5: "set `ttlSecondsAfterFinished` on the content-addressed Jobs ... a practical local-retention value such as `86400` seconds") so completed historical Jobs are garbage-collected; this is the cleanup half of the rerun contract, paired with content-addressed names per proposal §2 Q5 ("Do not rely on Flux prune as the primary cleanup mechanism") | none |
| Seed-Job rerun contract follows the same pattern | the same stale-completion risk exists for `seed-public-intake-form` (RCA §"Existing local patterns": "the ConfigMap can update while the stable completed Job does not execute again") | seed Job gains a content-addressed suffix tied to `data["seed.sql"]` plus the same TTL (proposal §2 Q2, Q6, §4 TG-3) | none |
| ConfigMap identity for the seed payload | stable name `seed-public-intake-form-payload` referenced from the Job's volume mount (RCA §"Existing local patterns") | unchanged — proposal §3: "Keep the ConfigMap name stable as `seed-public-intake-form-payload`; only the one-shot Job identity is content-addressed" and "Keep the volume reference to the stable ConfigMap name" | none |
| Hash computation is deterministic | n/a | proposal §2 Q2 specifies SHA-256 over (a) the `migrations/versions/` directory tree with deterministic path ordering and file bytes, truncated to 12 lowercase hex chars; (b) the ConfigMap `data["seed.sql"]` string, same truncation. Determinism is required for TG-2 ("rendered Alembic Job name is identical to the TG-1 rendered name") | none |
| Hash stamping site is the same boundary that owns local source materialization | n/a | proposal §2 Q3 locks `infra/scripts/render-gitops-source.py` between `_copy_gitops_tree(out)` and `_render_marker(out, gitops)`, which is the same boundary BUG-4's `--reseed-gitserver-only` already calls; no post-reseed hook, no live-cluster Job deletes (proposal §3 "Unmodified substrate") | none |

Risk on §6: **none** — gate criterion 6 (run-once contract preserved)
holds. The fix preserves "exactly one Pod per migration-tree advance"
through content-addressed Job identity and "no Job-object pile-up"
through `ttlSecondsAfterFinished`.

### 7. Anti-scope items — explicitly held out

| Surface | Status | Source |
|---|---|---|
| Helm / HelmRelease boundary for migrations | not introduced | proposal §5 anti-scope: "Do not switch to Helm" |
| CronJob runner for migrations | not introduced | proposal §5 anti-scope: "Do not add a CronJob runner" |
| Alembic SQL edits | not modified | proposal §5 anti-scope: "Do not modify the alembic SQL itself" |
| Flux GitRepository URL or source topology | not modified | proposal §5 anti-scope: "Do not change Flux's GitRepository URL" |
| `reseed_gitserver_only` imperative Job lifecycle | not modified | proposal §5 anti-scope: "Do not make `reseed_gitserver_only` delete, patch, or reapply application Jobs" |
| Compatibility shim preserving old stable Job names as aliases | not introduced | proposal §5 anti-scope: "Do not add a compatibility shim preserving the old stable Job names as aliases" |
| Channel `kustomization.yaml` file list | not modified | proposal §3 "Unmodified substrate": "remains a stable file list" — `alembic-migration-job.yaml` and `seed-public-intake-form.yaml` stay in place |
| Manifest filenames referenced by the Kustomization | not renamed | proposal §5 anti-scope: "Do not rename the manifest files referenced by the channel Kustomization" |
| New scripts | not added | proposal §6 budget "Not expected": "new scripts unless implementation proves `render-gitops-source.py` cannot safely own the stamping step" |
| Broad GitOps directory rewiring | not done | proposal §6 budget "Not expected" |
| Other one-shot Job manifests under `gitops/` (object-storage buckets, Loki bucket, step-CA configure, cert-manager startupapicheck, Crossplane appcluster Object) | not modified by BUG-9 | RCA §"Affected paths" enumerates them as "same rerun risk" candidates, but proposal §3 modified-files list and §6 diff budget restrict BUG-9 to the Alembic + seed pair; broader pattern adoption is out of scope |

## Supported-surface findings summary

| Gate | Verdict |
|---|---|
| 1. No public API change | PASS |
| 2. No env vars | PASS |
| 3. No DB migrations beyond what Alembic already provides | PASS |
| 4. No Pomerium / Authentik / OPAL changes | PASS |
| 5. Job's container args remain unchanged (no signature change) | PASS |
| 6. Run-once contract preserved (each new hash = new Job, old Jobs garbage-collected via TTL) | PASS |

## Findings

1. **No public API change.** Proposal §3 "Unmodified substrate"
   explicitly excludes API/daemon/web/repository/service/migration
   SQL/image edits. The diff budget (§6) caps changes at three files:
   one renderer script and two GitOps Job manifests under
   `gitops/channels/local/applications/server-manager/`. No HTTP,
   gRPC, or bridge endpoint is reachable from the modified files.
   The only externally observable name change is the rendered Alembic
   Job's `metadata.name`, and operator workflow per the proposal no
   longer requires that workflow's manual `kubectl delete job`
   (RCA §"Symptom + state").

2. **No env vars added.** The renderer's new helpers read inputs from
   the filesystem (`migrations/versions/` tree, seed YAML in the
   copied snapshot) and write outputs back into the snapshot
   directory; no `os.environ` access is introduced. The Alembic Job's
   `env` block (`DATABASE_URL` from `server-manager-postgres-url`
   secret) is preserved verbatim — the diff budget admits only
   metadata-block additions on the Job manifests (TTL plus optional
   debug labels).

3. **No DB migrations beyond Alembic's own.** Proposal §5 anti-scope
   forbids editing `alembic` SQL. The Job continues to invoke
   `alembic -c /app/alembic.ini upgrade heads` (manifest lines
   33-38), so any migration applied is one Alembic itself
   discovers under `migrations/versions/`. The TG-1 no-op migration
   exists *only* in the test plan to validate the rerun contract;
   it is not part of the production change set.

4. **No Pomerium / Authentik / OPAL change.** None of the three
   modified files lives under `gitops/channels/local/auth/**` or
   touches a Pomerium route, Authentik blueprint, or OPAL/OPA
   policy bundle. Authentication continues to flow through the
   recently restored claim chain (BUG-8 closure, commit `bdad3de`)
   without any input from this fix.

5. **Container args preserved.** The Pod template's `command`
   array is `["alembic", "-c", "/app/alembic.ini", "upgrade",
   "heads"]` pre and post (lines 33-38). The fix mutates only
   `metadata.name`, `metadata.labels`, and adds
   `spec.ttlSecondsAfterFinished` per proposal §3. Image, env,
   securityContext, resources, restartPolicy, backoffLimit, and
   the entire `spec.template.spec` block are byte-identical. Note:
   the user-supplied gate text shortens this to `alembic upgrade
   head` (singular, three tokens) — flagged as documentation
   wording only; the actual command string is unchanged either way.

6. **Run-once contract preserved.** Content-addressed Job names
   (proposal §2 Q1: `server-manager-alembic-migrate-<hash>` and
   `seed-public-intake-form-<hash>`) directly satisfy the
   "each new hash = new Job" half of the contract: a new desired
   `metadata.name` produces a new Kubernetes Job object, which
   creates exactly one new Pod, which executes `alembic upgrade
   heads` once, satisfying TG-1 and TG-3 acceptance. The
   "unchanged inputs do not spawn a redundant Pod" half is
   satisfied by hash determinism (TG-2 acceptance: "rendered
   Alembic Job name is identical"). The "old Jobs
   garbage-collected" half is satisfied by
   `ttlSecondsAfterFinished` on both Jobs (proposal §2 Q5),
   which the Kubernetes TTL controller honors per the docs the
   RCA cites. This is independent of Flux prune (proposal §2 Q5:
   "Do not rely on Flux prune as the primary cleanup
   mechanism"), so the cleanup behavior is local to the Job's own
   lifecycle and survives any reseed/reconcile timing variance.

## Out-of-scope items intentionally not addressed

- **Other one-shot Jobs flagged by the RCA** (object-storage bucket
  bootstraps under `gitops/channels/local/object-storage/buckets/`,
  Loki observability bucket, Step-CA configure-clusterissuer, the
  Crossplane appcluster `Object`-embedded provision Job, rendered
  cert-manager `startupapicheck`) — RCA §"Affected paths" notes
  they share the same stable-name rerun risk, but proposal §3 and
  §6 confine BUG-9 to the Alembic + public-intake-seed pair.
  Broader adoption can land in a follow-up if a future incident
  validates the need.

- **Helm/CronJob/external-runner alternatives** (RCA §"Solution
  candidates" B/E/F) — proposal §5 anti-scope rejects each;
  intervention point is locked to Job identity (Q1 candidate A).

- **Kustomize replacements / patches** for content-addressed names
  — proposal §3: "Do not introduce Kustomize replacements for this
  BUG-9 fix"; the renderer already owns full snapshot
  materialization, so direct structured YAML mutation is the
  chosen mechanism.

- **Reseed-time imperative Job lifecycle** — proposal §3
  "Unmodified substrate" and §5 anti-scope both bar
  `reseed_gitserver_only` from deleting/patching/reapplying
  application Jobs; the rerun contract lives in render-time naming,
  not in the operator script.

- **Image-tag-driven rerun** — discussed and discarded in proposal
  §2 Q1 in favor of content-addressed names; the static
  `init-113-local` image tag is unchanged.

## Verdict

**LOW** — the fix is a self-contained render-time YAML mutation in
`infra/scripts/render-gitops-source.py` plus metadata-only
additions (`ttlSecondsAfterFinished`, optional content-hash label)
on two GitOps Job manifests under
`gitops/channels/local/applications/server-manager/`. It changes
no public API, no env var, no DB migration, no Pomerium /
Authentik / OPAL resource, and no Job container `command`/`args`
or other Pod-template field. The rerun contract is preserved by
deterministic content-hashed Job names (each new
`migrations/versions/` tree or seed-SQL payload yields exactly one
new Job object and one Pod execution) and `ttlSecondsAfterFinished`
keeps completed historical Jobs from accumulating. All six
supported-surface gates pass.

SUPPORTED_SURFACE_DONE: plans/risk/bug-9-supported-surface.md
