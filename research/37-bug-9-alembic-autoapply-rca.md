# BUG-9 RCA: Alembic migrations do not auto-apply after gitserver reseed

## Symptom + state

After BUG-4's `--reseed-gitserver-only` path advances the in-cluster
gitserver to a newer rendered GitOps snapshot, Flux reconciles the snapshot
successfully but does not run `server-manager-alembic-migrate` again. The
database can remain at an older Alembic head even though the reseeded worktree
contains newer files under `migrations/versions/`.

Observed state from the bug report:

- `alembic_version` stayed at `wu_043_members_kind`.
- New migrations `wu-044_application_messages.py` and
  `wu-045_application_public_submit_notifications.py` were present in the
  gitserver snapshot.
- e2e test 19 failed with `relation "application_messages" does not exist`.
- Manual workaround was to delete and re-apply the Job:
  `kubectl delete job server-manager-alembic-migrate && kubectl apply -f .../alembic-migration-job.yaml`.

The current manifest is a plain Kubernetes `batch/v1` Job with a stable name:

- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:1-5`
  defines `kind: Job`, `metadata.name: server-manager-alembic-migrate`, and
  `namespace: server-manager`.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:28-38`
  runs `alembic -c /app/alembic.ini upgrade heads`.
- There are no `helm.sh/hook`, `helm.sh/hook-delete-policy`, Flux hook, or
  rerun annotations in the manifest.
- The image tag is currently static:
  `k3d-humility-local:5000/local/server-manager-api:init-113-local`
  at `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml:30`.

## Architecture review

The local channel is rendered into an in-cluster Git repository and reconciled
by Flux:

- `infra/scripts/render-gitops-source.py:202-225` renders the Flux
  `Kustomization` CR for the channel.
- That rendered CR sets `spec.prune`, `spec.wait`, and `spec.force: true`
  (`infra/scripts/render-gitops-source.py:211-217`).
- `gitops/channels/local/applications/server-manager/kustomization.yaml:14-15`
  includes both `alembic-migration-job.yaml` and
  `seed-public-intake-form.yaml`.
- The checked-in bootstrap sample in `gitops/flux/humility-local.yaml` also
  uses `prune: true` and `wait: true`.

The reseed entry point does not directly touch the migration Job:

- `infra/scripts/bring-up-local-channel.sh:439-452` validates the existing
  k3d cluster, then delegates to `install-flux-for-channel.sh
  --reseed-gitserver-only`.
- `infra/scripts/install-flux-for-channel.sh:500-510` renders a snapshot,
  ensures the git daemon exists, seeds the git daemon, applies source CRs, and
  waits for the `GitRepository` artifact revision.
- That reseed path does not call `request_kustomization_reconciliation`
  (`infra/scripts/install-flux-for-channel.sh:250-262`), does not wait for
  the Flux `Kustomization` (`infra/scripts/install-flux-for-channel.sh:301-309`),
  and does not delete/recreate any Jobs.
- Full install does request and wait for Kustomization reconciliation
  (`infra/scripts/install-flux-for-channel.sh:555-569`), but it also does not
  have a migration-specific rerun step.

Flux's documented behavior matches this architecture. Flux Kustomizations watch
GitRepository artifacts and apply manifests when the Git revision changes; with
`prune` enabled, resources missing from the current revision are deleted. Flux
also runs periodic server-side apply dry-runs to detect drift. Source:
<https://fluxcd.io/flux/components/kustomize/kustomizations/>.

Flux's Jobs guide calls out the exact class of issue: if Flux reconciles a Job,
it applies it once; later Job manifest updates are constrained by the Kubernetes
API because key Job fields are immutable. To update a Job, it must be removed
and reapplied. With `spec.force: true`, Flux recreates a Job when an immutable
field changes, which can force a rerun when something like the container image
tag changes. Source:
<https://fluxcd.io/flux/use-cases/running-jobs/>.

## Why one-shot Jobs are not re-run

The root cause is a mismatch between "GitOps source revision changed" and "a
stable Kubernetes Job object should execute again."

Kubernetes Jobs are one-off controllers. A Job creates Pods, tracks successful
completions, and becomes complete once the required completions are reached.
For the non-parallel/default case, one successful Pod is enough. Source:
<https://kubernetes.io/docs/concepts/workloads/controllers/job/>.

Once `server-manager-alembic-migrate` exists with `status.succeeded=1`, a later
Flux reconcile of the same `metadata.name` and same effective Job spec does not
create a new Job object and therefore does not create a new migration Pod. A
successful Job is not like a Deployment rollout controller; there is no
"restart because source changed" behavior on the same Job object.

`spec.force: true` is insufficient for this specific observed path because it
only helps when Flux attempts a patch that fails due to immutable fields. If
the rendered Job remains effectively unchanged to Kubernetes, Flux has nothing
to delete and recreate. If only files inside the already-built image's working
tree changed but the Job manifest's immutable pod template did not change, the
stable completed Job remains stable and complete.

Kubernetes can clean up finished Jobs with `ttlSecondsAfterFinished`, and if
the field is unset the TTL controller will not clean the Job after it finishes.
Source: <https://kubernetes.io/docs/concepts/workloads/controllers/job/> and
<https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/>.
The Alembic Job does not set TTL. Even if TTL were used, that would be a cleanup
mechanism, not a source-revision-to-migration-run contract by itself.

The manifest is also not a Helm hook. Helm hook Jobs become hooks only through
`helm.sh/hook` metadata annotations, and hook cleanup/recreation is controlled
by `helm.sh/hook-delete-policy`. Source:
<https://helm.sh/docs/topics/charts_hooks/>. The Alembic manifest has none of
those annotations and is applied by Flux Kustomize, not a Helm release.

## Existing local patterns

`seed-public-intake-form` follows the same one-shot pattern:

- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:1-11`
  defines a ConfigMap payload with inline SQL.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:254-258`
  defines a stable-name `batch/v1` Job named `seed-public-intake-form`.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml:300-334`
  waits for migrated tables and then runs `psql "$DATABASE_URL" -f /seed/seed.sql`.

The seed SQL has database-level idempotency around the current seed variants,
but the Kubernetes Job object itself has the same no-rerun property as the
Alembic Job. If the ConfigMap SQL changes from v1 to v2 after the original Job
already completed, the ConfigMap can update while the stable completed Job does
not execute again.

Other bucket/bootstrap Jobs also use stable names and idempotent commands.
They are less likely to fail as visibly because their commands generally do
`mc mb --ignore-existing`, but a changed desired bucket name or changed
bootstrap behavior has the same one-shot rerun risk.

## Solution candidates and tradeoffs

These are intervention points for the next proposal phase, not a selected fix.

### Candidate A: content-addressed Job names

Give one-shot Jobs names derived from the content that must trigger a run, such
as migration head, image digest, rendered source revision, or a short manifest
hash.

Tradeoffs:

- Strong GitOps fit: a new desired object name creates a new Kubernetes Job.
- Works naturally with completed Job immutability because each run is a new
  object.
- Requires a deterministic render-time source of the relevant content hash.
- Creates historical Job objects unless paired with TTL or pruning of old names.
- Needs careful naming for seed Jobs so data-idempotency and Job identity stay
  understandable.

Intervention points:

- `infra/scripts/render-gitops-source.py` if names are stamped during snapshot
  rendering.
- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  for migration Job naming and labels.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  if seed Jobs should follow the same pattern.

### Candidate B: split Flux Kustomizations for pre/post Jobs

Move migration Jobs into their own Flux Kustomization with `wait: true`,
`force: true`, and `dependsOn` ordering, matching Flux's documented pre-deploy
Job pattern.

Tradeoffs:

- Aligns with Flux's documented migration/deploy/post-deploy structure.
- Gives explicit ordering between migrations, application deployment, and
  post-deploy seeds.
- Still needs an immutable field change, name change, or cleanup mechanism to
  guarantee a rerun per relevant source change.
- Adds Flux object topology and dependency management.

Intervention points:

- `gitops/sources/local/kustomization.yaml` / rendered source Kustomization
  structure.
- New pre-deploy/deploy/post-deploy directories or Kustomization CRs under
  `gitops/channels/local`.
- Existing `gitops/channels/local/applications/server-manager/kustomization.yaml`.

### Candidate C: reseed script deletes and re-applies selected Jobs

Extend the BUG-4 reseed path so that after source revision and Flux reconcile,
it explicitly deletes/re-applies known one-shot Jobs such as Alembic and seed
Jobs.

Tradeoffs:

- Directly targets the operator workflow that exposed the bug.
- Keeps manifests simple and preserves stable Job names.
- Couples local reseed scripting to application bootstrap internals.
- Does not help non-reseed Flux updates unless all relevant updates go through
  that script.
- Needs explicit ordering and failure handling so seed Jobs do not run before
  migrations.

Intervention points:

- `infra/scripts/install-flux-for-channel.sh:500-510`
  (`reseed_gitserver_only`).
- `infra/scripts/install-flux-for-channel.sh:250-309`
  for Kustomization reconcile/wait helpers.
- Runtime validators that currently wait for completed Jobs, especially
  `infra/tests/validate_application_workloads_local.sh:337-345`.

### Candidate D: TTL cleanup on completed one-shot Jobs

Set `ttlSecondsAfterFinished` on selected Jobs so completed Job objects are
eligible for Kubernetes cleanup.

Tradeoffs:

- Reduces retained completed Job objects.
- Can make a later Flux reconcile recreate a missing Job with the same stable
  name.
- Does not tie rerun timing to a specific Git revision or migration head.
- If TTL expires while Flux still reconciles the same source, Jobs may rerun
  repeatedly on interval unless the controller inventory and health behavior
  are understood carefully.

Intervention points:

- Any stable one-shot Job manifest under `gitops/`.
- Flux Kustomization wait/health behavior for Jobs.

### Candidate E: Helm hook or HelmRelease-managed migration

Move migration execution into a Helm-managed hook with explicit hook and
delete-policy annotations.

Tradeoffs:

- Helm has native hook lifecycle concepts for install/upgrade Jobs.
- Hook deletion policy can clean up completed hook Jobs before the next hook
  run or immediately after success.
- Introduces Helm ownership for an area currently managed by Kustomize.
- Would need a clear release boundary and chart structure; otherwise it adds
  a second deployment model only for migrations.

Intervention points:

- A future Helm chart or HelmRelease boundary for server-manager.
- Migration Job template annotations:
  `helm.sh/hook` and `helm.sh/hook-delete-policy`.

### Candidate F: CronJob or external runner with run-once semantics

Use a CronJob or an external migration runner that checks the database head and
applies migrations when needed.

Tradeoffs:

- Can make migration application independent from one-shot Job object identity.
- Needs its own locking/idempotency/error-reporting contract.
- Periodic polling can hide deployment ordering issues unless tightly gated.
- More moving parts than a Flux/Kubernetes Job if the only needed trigger is
  source revision advancement.

Intervention points:

- New runtime controller/runner or CronJob manifest.
- Database migration lock/audit behavior.
- Application readiness gates.

## Affected paths

Directly affected server-manager Jobs:

- `gitops/channels/local/applications/server-manager/alembic-migration-job.yaml`
  - stable one-shot migration Job; observed failure path.
- `gitops/channels/local/applications/server-manager/seed-public-intake-form.yaml`
  - ConfigMap plus stable one-shot seed Job; same rerun risk for seed SQL
  changes.
- `gitops/channels/local/applications/server-manager/object-storage-bucket-job.yaml`
  - stable one-shot bucket bootstrap Job; command is idempotent but still
  stable-name one-shot.

Other direct `kind: Job` manifests under `gitops/`:

- `gitops/channels/local/object-storage/buckets/job.yaml`
  - stable `create-sample-bucket` bootstrap Job.
- `gitops/channels/local/object-storage/buckets/backup-job.yaml`
  - stable `create-backup-bucket` bootstrap Job.
- `gitops/channels/local/observability/loki/bucket-job.yaml`
  - stable `loki-observability-bucket` bootstrap Job; sets
  `ttlSecondsAfterFinished: 86400`.
- `gitops/channels/local/tls/local-issuer/configure-step-clusterissuer.yaml`
  - stable `configure-step-clusterissuer` Job that applies the Step
  ClusterIssuer.
- `gitops/channels/local/tls/step-ca/rendered/step-certificates-1.30.1.yaml`
  - rendered chart Job `step-ca`.
- `gitops/channels/local/tls/cert-manager/rendered/cert-manager-v1.20.2.yaml`
  - rendered chart Job `cert-manager-startupapicheck`.

Nested Job manifests that are not direct top-level Job documents:

- `gitops/channels/local/app-clusters/compositions/appcluster-k3d-local.yaml`
  contains a Crossplane `Object` whose embedded manifest is a `batch/v1` Job
  named `provision-appcluster-local`.

## RCA conclusion

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
