# Audit Risk — INIT-102

## Verdict
LOW

## Summary

Audit risk is LOW. The current proposal covers the requested presence/checklist surface: strict channel schema extension, schema versioning posture, post-install Flux wiring, pinned Flux/SOPS/age tooling, local k3d reconciliation proof, in-cluster Git source mechanics, bootstrap-only SOPS+age boundary, INIT-009 disposal, slice-level acceptance criteria, anti-scope, rollback, and observability. No PARTIAL or MISSING load-bearing artifact was found.

## Findings table

| ID | Category | Severity | Finding | Proposal cite | Recommendation |
|---|---|---:|---|---|---|
| none | n/a | LOW | No audit-presence findings. | n/a | No action required for audit convergence. |

## Coverage matrix

| Checklist item | Status | Proposal cite | Notes |
|---|---|---|---|
| Channel schema additions for `gitops` block defined exactly | PRESENT | `.pipeline/proposal.md:181-301` | Source schema, resolved schema behavior, required fields, patterns, defaults, and concrete `local.yaml` block are specified. |
| Schema versioning posture (`schema_version` stays; no breaking change without bump) | PRESENT | `.pipeline/proposal.md:189-192` | `schema_version` remains `1`; breaking `gitops` field/semantic changes require `schema_version: 2`. |
| `additionalProperties: false` enforced on the new `gitops` block | PRESENT | `.pipeline/proposal.md:223-278` | `$defs.gitops` sets `additionalProperties: false`. |
| Interaction with existing `cluster.target` specified | PRESENT | `.pipeline/proposal.md:181-187`, `.pipeline/proposal.md:303-311`, `.pipeline/proposal.md:342-356` | `k3d-local` requires `gitops`; `vultr-vms` may omit it; post-install requires `cluster.target == "k3d-local"`. |
| `gitops/` directory layout has every file path enumerated | PRESENT | `.pipeline/proposal.md:50-100`, `.pipeline/proposal.md:102-139` | File surface table and final tree enumerate the layout. |
| Flux base manifests source named with version pin | PRESENT | `.pipeline/proposal.md:141-153`, `.pipeline/proposal.md:613-616` | `gotk-components.yaml` is generated from pinned `flux v2.8.6` via `flux install --export`. |
| SOPS+age `.sops.yaml` location and `creation_rules` explicit | PRESENT | `.pipeline/proposal.md:519-532` | Location, `path_regex`, `encrypted_regex`, and age recipient shape are shown. |
| Channel-template extension binds to one approach, post-install script per D8 | PRESENT | `.pipeline/proposal.md:313-379` | Binds to `infra/scripts/install-flux-for-channel.sh`; invocation point is `bring-up-local-channel.sh` after k3d readiness. |
| Toolchain installer lists exact CLI versions for `flux`, `sops`, `age` | PRESENT | `.pipeline/proposal.md:651-681` | Pins `flux v2.8.6`, `sops v3.12.2`, `age v1.3.1`, and `age-keygen v1.3.1`. |
| Real Flux install in local k3d at done-state | PRESENT | `.pipeline/proposal.md:20-34`, `.pipeline/proposal.md:636-645`, `.pipeline/proposal.md:879-927` | Done state is live local k3d Flux reconciliation, not render-only verification. |
| Flux Kustomization `Ready` assertion in harness | PRESENT | `.pipeline/proposal.md:891-894` | Harness waits for `Kustomization/humility-local` Ready with current `observedGeneration`. |
| Test target manifest reconciled with exact assertion | PRESENT | `.pipeline/proposal.md:59-66`, `.pipeline/proposal.md:901-906` | Sentinel namespace/configmap and snapshot marker assertions are named. |
| SOPS-decrypted test secret reconciled with exact assertion | PRESENT | `.pipeline/proposal.md:501-512`, `.pipeline/proposal.md:604-611`, `.pipeline/proposal.md:907-910` | `Secret/gitops-sops-sentinel` must exist and decode to expected sentinel values. |
| Bring-up and tear-down idempotent | PRESENT | `.pipeline/proposal.md:358-370`, `.pipeline/proposal.md:883-884`, `.pipeline/proposal.md:922-927` | Second bring-up and second delete must succeed without duplicate resources or manual cleanup. |
| In-cluster `git daemon` Deployment shape specified | PRESENT | `.pipeline/proposal.md:381-418` | Namespace, PVC, Deployment, Service, replicas, port, image, digest, command, volume, and protocol URL are specified. |
| Seeding mechanism bound to one approach | PRESENT | `.pipeline/proposal.md:420-463` | Host-side snapshot script is the binding mechanism; sidecar and hostPath are excluded. |
| Re-seed cadence specified | PRESENT | `.pipeline/proposal.md:465-478` | Manual reseed via `seed-local-git-source.sh --reconcile`; no sidecar or scheduled host polling. |
| Branch/ref naming convention for Flux `GitRepository` specified | PRESENT | `.pipeline/proposal.md:288-300`, `.pipeline/proposal.md:465-475` | Channel stores `refs/heads/main`; renderer emits Flux `branch: main`. |
| Failure mode when local repo and in-cluster Git diverge documented | PRESENT | `.pipeline/proposal.md:480-492` | Stale snapshot, Git daemon restart, and invalid Git content failure modes are documented. |
| Concrete encrypted files in INIT-102 specified | PRESENT | `.pipeline/proposal.md:494-498` | Exactly one encrypted sentinel file is in scope. |
| Age key file path and permissions specified | PRESENT | `.pipeline/proposal.md:545-555` | Operator key path is `~/.config/sops/age/local.txt` with mode `0600`. |
| Age Secret name and namespace specified | PRESENT | `.pipeline/proposal.md:571-589` | Secret `sops-age` in namespace `flux-system`, key `age.agekey`. |
| Manual operator step explicit and idempotent | PRESENT | `.pipeline/proposal.md:557-580` | Bootstrap script creates/verifies key, writes/verifies `.sops.yaml`, encrypts sentinel, and applies Secret with dry-run/apply. |
| Boundary "bootstrap-only, runtime is INIT-103/Infisical" reinforced | PRESENT | `.pipeline/proposal.md:515-517`, `.pipeline/proposal.md:536-543`, `.pipeline/proposal.md:591-593`, `.pipeline/proposal.md:998-999` | Runtime secrets are excluded and Infisical runtime ownership is assigned to INIT-103. |
| `flux install --export` output committed to repo | PRESENT | `.pipeline/proposal.md:141-153`, `.pipeline/proposal.md:613-616`, `.pipeline/proposal.md:868-874` | `gotk-components.yaml` is committed and treated as the Flux lockfile. |
| Component subset explicit yes/no | PRESENT | `.pipeline/proposal.md:618-627` | Source and kustomize controllers included; Helm, notification, and image controllers excluded. |
| Image tags pinned per D10 | PRESENT | `.pipeline/proposal.md:629-634`, `.pipeline/proposal.md:843-855` | Flux controller image tags and local proof digests are named. |
| Installation order vs cluster bring-up specified | PRESENT | `.pipeline/proposal.md:636-645` | Flux install starts after local cluster and kubeconfig creation. |
| INIT-009 discarded paths explicit | PRESENT | `.pipeline/proposal.md:788-815`, `.pipeline/proposal.md:827-834` | INIT-009 paths and current stale `k8s/` paths to delete are listed. |
| Reference branch preservation called out | PRESENT | `.pipeline/proposal.md:788-799` | Reference branch `feat/init-009-gitops-substrate` and SHA are named. |
| No `archived/` subdir or compatibility shim | PRESENT | `.pipeline/proposal.md:817-825`, `.pipeline/proposal.md:827-834` | Salvage is by rederived ideas only; no symlinks or archived copies. |
| Each of six slices has explicit ACs | PRESENT | `.pipeline/proposal.md:687-786` | All six slices include acceptance criteria. |
| Each AC is locally executable | PRESENT | `.pipeline/proposal.md:691-694`, `.pipeline/proposal.md:705-709`, `.pipeline/proposal.md:720-727`, `.pipeline/proposal.md:738-744`, `.pipeline/proposal.md:756-762`, `.pipeline/proposal.md:773-782` | ACs are local scripts, local schema/render tests, or local k3d harness checks. |
| Dependency DAG is acyclic | PRESENT | `.pipeline/proposal.md:696-698`, `.pipeline/proposal.md:711-712`, `.pipeline/proposal.md:729-730`, `.pipeline/proposal.md:746-748`, `.pipeline/proposal.md:764-766`, `.pipeline/proposal.md:784-786` | Dependencies progress from 102.01 through 102.06. |
| Anti-scope per slice | PRESENT | `.pipeline/proposal.md:696-697`, `.pipeline/proposal.md:711-712`, `.pipeline/proposal.md:729-730`, `.pipeline/proposal.md:746-748`, `.pipeline/proposal.md:764-765`, `.pipeline/proposal.md:784-785` | Each slice has explicit anti-scope. |
| `flux` CLI version pinned | PRESENT | `.pipeline/proposal.md:152-153`, `.pipeline/proposal.md:660-662`, `.pipeline/proposal.md:837-840` | Pin is `v2.8.6`. |
| `sops` CLI version pinned | PRESENT | `.pipeline/proposal.md:662-664`, `.pipeline/proposal.md:858-865` | Pin is `v3.12.2`. |
| `age` CLI version pinned | PRESENT | `.pipeline/proposal.md:662-664`, `.pipeline/proposal.md:858-865` | Pin is `v1.3.1`; `age-keygen` is also pinned. |
| Flux component image tags pinned | PRESENT | `.pipeline/proposal.md:629-634`, `.pipeline/proposal.md:843-855` | Source/kustomize controller tags and digests are named. |
| Lockfile expectation stated for `gotk-components.yaml` | PRESENT | `.pipeline/proposal.md:868-877` | Committed, reviewed, regenerated only with pinned Flux and exact component selector. |
| Crossplane (INIT-106) anti-scope | PRESENT | `.pipeline/proposal.md:992-997` | Crossplane and app-cluster provisioning are excluded. |
| Infisical runtime (INIT-103) anti-scope | PRESENT | `.pipeline/proposal.md:998-999` | Runtime secret sync is excluded. |
| Object storage (INIT-104) anti-scope | PRESENT | `.pipeline/proposal.md:1000-1001` | Object storage and S3 app paths are excluded. |
| cert-manager / DNS / TLS (INIT-105) anti-scope | PRESENT | `.pipeline/proposal.md:1002-1003` | Certificate, DNS, TLS, and issuer work is excluded. |
| Container delivery (INIT-108) anti-scope | PRESENT | `.pipeline/proposal.md:1007-1008` | Image build/registry/image automation is excluded. |
| CI/CD (INIT-109) anti-scope | PRESENT | `.pipeline/proposal.md:1009-1010` | Buildkite and release promotion are excluded. |
| Ingress (INIT-110) anti-scope | PRESENT | `.pipeline/proposal.md:1011-1012` | Ingress and Pomerium routes are excluded. |
| Data plane (INIT-111) anti-scope | PRESENT | `.pipeline/proposal.md:1013-1013` | Postgres, migrations runtime, and database operators are excluded. |
| Backup (INIT-112) anti-scope | PRESENT | `.pipeline/proposal.md:1014-1014` | Backup, restore, snapshots, and disaster recovery jobs are excluded. |
| App workloads (INIT-113) anti-scope | PRESENT | `.pipeline/proposal.md:1015-1016` | API, Discord daemon, workers, and beta guild runtime are excluded. |
| Auth (INIT-114) anti-scope | PRESENT | `.pipeline/proposal.md:1017-1017` | Authentik, OIDC, OPAL/Cedar, and login flows are excluded. |
| Access policy (INIT-115) anti-scope | PRESENT | `.pipeline/proposal.md:1018-1019` | Flux tenant RBAC and least-privilege service accounts beyond default install are excluded. |
| Tenant isolation (INIT-116) anti-scope | PRESENT | `.pipeline/proposal.md:1020-1021` | Namespace boundary and per-tenant GitOps delegation are excluded. |
| Observability (INIT-117) anti-scope | PRESENT | `.pipeline/proposal.md:1022-1023` | Notifications, alerts, dashboards, OTLP, and `notification-controller` are excluded. |
| Installer covers `flux`, `sops`, `age`; standalone `kustomize` decision bound | PRESENT | `.pipeline/proposal.md:651-670` | Existing installer is extended; standalone `kustomize` is explicitly not installed. |
| Each install step idempotent and version-checked | PRESENT | `.pipeline/proposal.md:672-681` | `--check`, `--install`, SHA verification, no overwrite of correct binaries, and second-run idempotency are specified. |
| Current-state risk INIT-102 reduces is named | PRESENT | `.pipeline/proposal.md:929-937` | Names no accepted GitOps path, stale hard-env `k8s/`, and SOPS runtime-store confusion. |
| Blast radius added is named | PRESENT | `.pipeline/proposal.md:939-950` | Names Flux controllers/CRDs/RBAC, age key SPOF, in-cluster Git daemon, and stale snapshots. |
| Migration path stated | PRESENT | `.pipeline/proposal.md:952-955` | None; first accepted GitOps substrate after D8 reset. |
| Rollback path stated | PRESENT | `.pipeline/proposal.md:957-973` | Flux custom resources, Flux uninstall, namespaces, and local channel deletion are specified. |
| Observability stated | PRESENT | `.pipeline/proposal.md:975-983` | Controller logs, Flux get commands, and Git daemon logs are listed. |

## Convergence statement

INIT-102 converges under the audit checklist. Every requested presence item is PRESENT in the current proposal, and no PARTIAL or MISSING load-bearing artifact remains. The audit gate can pass with LOW risk.
