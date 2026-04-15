# GitOps Foundation — Phase 1 Research

## Bottom line

The GitOps Foundation implementation requires a Flux CD-driven,
path-based multi-environment layout that enforces Git as the sole
desired-state system. The strongest pattern for this project is a
three-layer Kustomize structure (`base → overlays → clusters`) with
per-cluster Flux roots, per-environment directory isolation, and a hard
CI/CD boundary where Buildkite validates but never mutates clusters.

## 1. Flux CD architecture and reconciliation model

Flux CD v2 is a set of specialized controllers installed per-cluster:

- **source-controller** watches Git repositories (or Helm/OCI sources)
  and makes them available as artifacts inside the cluster
- **kustomize-controller** applies Kustomize overlays from source
  artifacts to the cluster, handling dependency ordering and health
  checks
- **helm-controller** reconciles HelmRelease objects against chart
  sources
- **notification-controller** dispatches alerts and receives webhooks

The reconciliation loop is pull-based. Each cluster's Flux installation
polls its configured Git source at a defined interval. When the source
changes, the kustomize-controller renders and applies the new desired
state. Drift from the desired state is corrected automatically on the
next reconciliation cycle.

Key architectural properties:

- **Per-cluster installation**: Each cluster runs its own Flux
  controllers. There is no central Flux instance that pushes to remote
  clusters.
- **GitRepository + Kustomization pair**: The standard pattern is one
  `GitRepository` source pointing at the repo, and one or more
  `Kustomization` resources selecting paths within that source.
- **Prune and wait**: `prune: true` removes objects from the cluster
  that are no longer in Git. `wait: true` blocks until applied objects
  report ready.
- **Interval tuning**: `GitRepository.spec.interval` controls how often
  the source is polled (typically 1m). `Kustomization.spec.interval`
  controls how often the desired state is re-applied (typically 5-10m).

For this project, the reconciliation cadence should be:

- GitRepository interval: `1m` (fast detection of Git changes)
- Kustomization interval: `10m` (re-apply desired state to catch drift)
- Kustomization timeout: `5m` (fail health checks that hang)

These intervals balance responsiveness against API server load for a
small-to-medium cluster count.

## 2. GitOps multi-environment layout patterns

Three dominant patterns exist for multi-environment GitOps:

### Branch-based separation

Each environment gets its own long-lived branch (`dev`, `staging`,
`main`). Promotion is a merge from one branch to another.

Strengths: strong isolation per environment, familiar Git workflow.
Weaknesses: merge conflicts accumulate, promotion is error-prone, cherry-
picking across branches creates drift, hard to see all environments in
one view.

### Path-based separation (recommended)

All environments live in one branch under distinct directory paths.
Promotion is a PR that changes files in the target environment path.

Strengths: single branch of truth, easy to compare environments, no
merge conflicts between environments, promotion is a normal PR review.
Weaknesses: repo-level compromise affects all environments, requires
path-based access controls.

### Repo-based separation

Each environment gets its own repository. Promotion copies or syncs
manifests between repos.

Strengths: strongest isolation, separate access controls per repo.
Weaknesses: operational overhead of multiple repos, sync tooling
required, harder to maintain consistency.

**Decision**: Path-based separation is the right fit for this project.
The team is small, the environment count is bounded (dev, staging,
production), and the single-branch model eliminates merge drift. Repo-
level access controls (CODEOWNERS, branch protection) provide sufficient
isolation for production paths.

## 3. Kustomize overlay patterns

Kustomize provides a layering model that maps naturally to the
`base → overlays → clusters` structure:

- **base/**: Contains environment-neutral, reusable building blocks.
  These are Kustomization directories that define shared resources
  (namespaces, policies, platform defaults, controller contracts)
  without knowing which environment consumes them.

- **overlays/**: Compose bases for a specific environment and cluster
  role. Each overlay references `base/` and adds environment-specific
  configuration via `configMapGenerator`, patches, or additional
  resources. The overlay is where scale, feature flags, and role-
  specific wiring live.

- **clusters/**: Thin per-cluster roots that select the right overlay,
  add cluster-specific Flux objects (GitRepository, Kustomization), and
  define ordering. The cluster root is the entry point for that
  cluster's Flux installation.

Key Kustomize patterns used in this implementation:

- `configMapGenerator` with `disableNameSuffixHash: true` for explicit
  naming of metadata ConfigMaps (platform defaults, controller
  contracts, boundary policies)
- `resources:` references to compose base directories
- Relative path references (`../../../base/`) from overlays back to base
- Per-cluster `generatorOptions` for cluster-root-level metadata

The layering keeps shared intent in `base/`, environment variation in
`overlays/`, and cluster-specific Flux wiring in `clusters/`.

## 4. SealedSecrets integration

The platform decisions overlay locks Flux CD as the sole reconciler.
Secrets management must work within the GitOps model — secrets must be
expressible as Git-committed resources that Flux can reconcile.

SealedSecrets is the standard Flux-compatible solution:

- A SealedSecrets controller runs in-cluster and holds the decryption
  key
- Developers encrypt secrets client-side using `kubeseal`, producing
  `SealedSecret` resources
- `SealedSecret` resources are committed to Git like any other manifest
- The controller decrypts them into standard Kubernetes `Secret` objects
  inside the cluster
- Key rotation is managed by the controller; sealed values are
  re-encrypted periodically

Integration points with the GitOps Foundation layout:

- The SealedSecrets controller installation belongs in
  `base/controllers/` or as a Flux `HelmRelease` in the cluster root
- Encrypted `SealedSecret` resources belong in the appropriate overlay
  or cluster-root path
- The proposal's interface constraint applies: "A cluster root may rely
  on at most one secret-reconciliation path at any one time"

For the initial implementation, secret-related resources are not yet
present. The `base/controllers/` Kustomization and cluster-root
manifests provide the structural slots where SealedSecrets resources
will land when the secrets initiative is implemented.

## 5. Reconciliation cadence decisions

The implementation uses these specific intervals:

| Resource | Interval | Rationale |
|----------|----------|-----------|
| GitRepository | 1m | Fast detection of new commits; polling overhead is minimal for a single repo |
| Kustomization | 10m | Drift correction cadence; re-applies desired state even without source changes |
| Kustomization timeout | 5m | Prevents health-check hangs from blocking the reconciliation loop |

These intervals are environment-independent in the initial
implementation. Production may later tighten the Kustomization interval
for faster drift correction or add webhook-driven reconciliation to
reduce polling latency.

The `prune: true` setting is enabled on all Kustomization resources.
This means removing a manifest from Git causes Flux to delete the
corresponding object from the cluster. This is essential for GitOps
correctness — without pruning, Git removals would leave orphaned objects
in clusters.

## 6. Existing implementation reference

The 38 files under `k8s/` implement the patterns researched above:

- `k8s/base/` — 7 files defining platform defaults, controller
  contracts, namespace declarations, and boundary policies as
  Kustomize-generated ConfigMaps
- `k8s/overlays/` — 6 files composing base for each environment/role
  combination (dev/staging/production × control-cluster/app-cluster)
- `k8s/clusters/` — 24 files providing per-cluster Flux roots with
  GitRepository + Kustomization pairs, manifest directories, bootstrap
  slots, and Crossplane claim slots
- `k8s/tests/test_gitops_foundation.sh` — 256-line acceptance test
  validating layering, environment paths, two-tier model, Flux scoping,
  and Buildkite boundary

## Sources

- Flux CD documentation: https://fluxcd.io/flux/
- Kustomize documentation: https://kustomize.io/
- SealedSecrets: https://sealed-secrets.netlify.app/
- Platform decisions overlay: `plans/platform-decisions-overlay.md`
- GitOps Foundation proposal: `plans/proposals/gitops-foundation.md`
- Platform Bootstrap hookpoints: `plans/research/platform-bootstrap-hookpoints.md`
- Existing k8s/ implementation files (38 files)
- Risk assessments: `plans/risk/gitops-foundation-{audit,scope,shortcut}.md`
