# Phase 5 Index - Environment-Agnostic Deployment Substrate

Phase 5 rebuilds the deployment substrate around one governing rule:

**Local is the first deployment target, not a simulation.**

The same stack runs locally and remotely. Channels carry provider and endpoint
configuration; they do not create architecture exceptions. Kubernetes is
self-managed k3s everywhere: k3d locally and k3s on Vultr Cloud Compute VMs
remotely. SOPS+age is bootstrap-only. Infisical is the runtime secret store.

## Status Legend

| Status | Meaning |
| --- | --- |
| `pending` | Not started in the corrected pipeline |
| `research` | Phase 1 problem/component research in progress |
| `synthesis` | Phase 2 project-context synthesis in progress |
| `proposal` | Phase 3 proposal/risk iteration in progress |
| `hookpoints` | Phase 5 hookpoint research in progress |
| `implementation` | Code/test implementation in progress |
| `done` | Implemented, reviewed, and accepted |

## Initiative Table

| INIT | Name | Scope | Dependencies | Local First | Magnitude | Status |
| --- | --- | --- | --- | --- | --- | --- |
| INIT-100 | Phase 5 reset | Delete wrong-shaped INIT-008/009/017 from main path, preserve reference branches, land D8 canon, replace old Phase 5 tracker | none | reset gate | S | done |
| INIT-101 | Self-managed k3s control cluster | k3d local control cluster; OpenTofu plus Vultr VMs plus cloud-init k3s remote control cluster contract | 100 | yes | XL | done |
| INIT-102 | GitOps substrate | Flux, Kustomize channel overlays, SOPS+age bootstrap-only, real reconciliation in local k3d | 101 | yes | L | done |
| INIT-103 | Infisical runtime secret store | Infisical, Infisical Operator, InfisicalSecret CRDs, RBAC, runtime secret ownership | 102 | yes | L | done |
| INIT-104 | S3-compatible storage layer | MinIO local, Vultr Object Storage remote contract, same S3 SDK path, credentials through Infisical | 103 | yes | M | done |
| INIT-105 | TLS and DNS automation | cert-manager, local step-ca issuer, local DNS/CoreDNS, remote ExternalDNS/Cloudflare and ACME contract | 102, 103 | yes | L | done |
| INIT-106 | Application cluster provisioning | Crossplane app-cluster claims for k3s targets, local-channel behavior, remote Vultr VM+k3s compositions | 101, 102, 103 | yes | XL | done |
| INIT-107 | Cluster security baseline | NetworkPolicies, PSS, RBAC, service-account boundaries, secret access, policy tests | 102, 106 | yes | L | done |
| INIT-108 | Container delivery and registry | Dockerfiles, local image load, channel-aware tags, registry decision with GHCR recommended | 101, 102 | yes | L | done |
| INIT-109 | CI/CD via Buildkite | Buildkite pipeline, local agent, remote agent contract, Flux handoff | 102, 108 | yes | L | done |
| INIT-110 | Ingress with Kong | Kong controller, local hostnames/TLS, route conventions, remote equivalent | 105, 107 | yes | M | done |
| INIT-111 | Data plane | CloudNativePG, Atlas SQL-first migrations, pg_stat_statements, DB credentials via Infisical | 103, 104, 107 | yes | L | done |
| INIT-112 | Backup and DR | CNPG backups to S3-compatible storage, RPO/RTO, restore drill, deletion safety | 104, 111 | yes | L | done |
| INIT-113 | Application workloads | Deploy api and discord workloads; local bot uses beta guild, remote uses Humility | 103, 108, 110, 111 | yes | XL | done |
| INIT-114 | Auth stack | Authentik, OPAL/Cedar, Pomerium, identity claims, route and policy integration | 103, 110, 113 | yes | XL | done |
| INIT-115 | Access policy and service identity | Pomerium policy-as-code, break-glass, Smallstep scope, service identity, service-mesh decision | 107, 114 | yes | M/L | done |
| INIT-116 | Tenant and channel isolation | Operationalize tenant/channel isolation across cluster, namespace, DB, object storage, Discord identity | 106, 111, 113, 114 | yes | L | done |
| INIT-117 | Observability stack | Prometheus + Grafana + Alertmanager + OpenTelemetry Collector + Loki; metrics from CNPG/Crossplane/Flux/Cedar/Authentik/Kong/api/discord; tenant-aware dashboards | 102, 107, 116 | yes | XL | done |

## Dependency Order

```text
INIT-100
  -> INIT-101
    -> INIT-102
      -> INIT-103
        -> INIT-104
        -> INIT-105
        -> INIT-106
          -> INIT-107
      -> INIT-108
        -> INIT-109
      -> INIT-110
      -> INIT-111
        -> INIT-112
      -> INIT-113
        -> INIT-114
          -> INIT-115
          -> INIT-116
          -> INIT-117
```

Parallelism is allowed only after each initiative's proposal and risk gate make
the dependency safe. The default execution order is the table order.

## Citation Crosswalk

| INIT | Audit rows addressed | Governing memory / source |
| --- | --- | --- |
| 100 | `AUD-03`, `AUD-08`, `AUD-22`, `AUD-37`, `AUD-38`, `AUD-59`, `AUD-62`, `AUD-63`, `AUD-64`, `AUD-67` | `environment-agnostic-stack.md`, `channel-template-pattern.md` |
| 101 | `AUD-01`, `AUD-02`, `AUD-03`, `AUD-04`, `AUD-05`, `AUD-06`, `AUD-09`, `AUD-10`, `AUD-22`, `AUD-59`, `AUD-67` | `environment-agnostic-stack.md`, `two-tier-cluster-architecture.md` |
| 102 | `AUD-11`, `AUD-12`, `AUD-13`, `AUD-14`, `AUD-60`, `AUD-61`, `AUD-62` | `channel-template-pattern.md`, `environment-agnostic-stack.md` |
| 103 | `AUD-37`, `AUD-38`, `AUD-39`, `AUD-62`, `AUD-69` | `environment-agnostic-stack.md`, `secrets-and-domains.md`, deleted-history `5781727`/`be89f7b` |
| 104 | `AUD-05`, `AUD-30`, `AUD-48`, `AUD-49`, `AUD-50` | `environment-agnostic-stack.md`, `plans/research/self-hosted-s3.md` |
| 105 | `AUD-23`, `AUD-24`, `AUD-36`, `AUD-40` | `environment-agnostic-stack.md`, `secrets-and-domains.md`, `plans/research/pomerium-smallstep.md` |
| 106 | `AUD-15`, `AUD-16`, `AUD-17`, `AUD-18`, `AUD-19`, `AUD-20`, `AUD-21`, `AUD-22`, `AUD-26`, `AUD-63` | `two-tier-cluster-architecture.md`, `environment-agnostic-stack.md`, `channel-template-pattern.md` |
| 107 | `AUD-18`, `AUD-25`, `AUD-26`, `AUD-41`, `AUD-57`, `AUD-66` | `two-tier-cluster-architecture.md`, `environment-agnostic-stack.md` |
| 108 | `AUD-42`, `AUD-43`, `AUD-46`, `AUD-47`, `AUD-51` | `platform-stack.md`, `plans/research/buildkite-capabilities.md` |
| 109 | `AUD-42`, `AUD-43`, `AUD-44`, `AUD-45`, `AUD-46` | `platform-stack.md`, `plans/research/buildkite-capabilities.md` |
| 110 | `AUD-27`, `AUD-33`, `AUD-35`, `AUD-39`, `AUD-65` | `environment-agnostic-stack.md`, deleted-history `5781727` |
| 111 | `AUD-28`, `AUD-29`, `AUD-30`, `AUD-64` | `plans/research/database-stack.md`, `environment-agnostic-stack.md` |
| 112 | `AUD-30`, `AUD-48`, `AUD-49`, `AUD-70` | `plans/research/self-hosted-s3.md`, `environment-agnostic-stack.md` |
| 113 | `AUD-31`, `AUD-32`, `AUD-64`, `AUD-65` | `discord-registration.md`, `environment-agnostic-stack.md` |
| 114 | `AUD-33`, `AUD-34`, `AUD-35`, `AUD-39`, `AUD-40`, `AUD-41`, `AUD-65` | `plans/platform-decisions-overlay.md`, `plans/research/pomerium-smallstep.md`, deleted-history `5781727` |
| 115 | `AUD-36`, `AUD-39`, `AUD-40`, `AUD-41`, `AUD-66`, `AUD-69` | `plans/research/pomerium-smallstep.md`, `feedback-escalation-bar.md` |
| 116 | `AUD-06`, `AUD-07`, `AUD-21`, `AUD-32`, `AUD-68` | `channel-template-pattern.md`, `environment-agnostic-stack.md`, `discord-registration.md` |
| 117 | `AUD-52`, `AUD-53`, `AUD-54`, `AUD-55`, `AUD-56`, `AUD-57` | `environment-agnostic-stack.md`, deleted-history `3426d61`/`5781727`/`be89f7b` |

## Operating Rules

1. Local is a deployment target. Every initiative must deploy a real component
   into the local channel as part of done state.
2. No local special exceptions. Channel config may change providers,
   endpoints, credentials, resource sizes, DNS provider, TLS issuer, and
   Discord guild class; it may not change component identity.
3. Self-managed k3s everywhere. Local uses k3d. Remote uses k3s on Vultr VMs.
   VKE is superseded.
4. SOPS+age is bootstrap-only. Runtime secrets go through Infisical.
5. Crossplane provisions app-cluster targets as k3s-based clusters or accepted
   local-channel equivalents, not VKE clusters.
6. Wrong-shaped work is deleted from the main path, not wrapped. Branches
   `feat/init-008-platform-bootstrap`, `feat/init-009-gitops-substrate`, and
   `feat/init-017-crossplane` remain references only.
7. No hard `dev/staging/production` environment roots. Channels with
   inheritance, exposure, tenant, and provider/endpoint config are the only
   environment model.
8. No deferred stubs. Empty handoff paths are allowed only when the owning INIT
   is named and the path has no runtime behavior.
9. No visible Discord writes during Phase 5 without explicit per-action user
   approval. Local workload testing targets the beta guild.
10. Do not re-litigate locked choices: Vultr, OpenTofu, Crossplane, Flux,
    Buildkite, Authentik, OPAL/Cedar, Pomerium, channel templates, and
    two-tier architecture.

## Completion Criteria

Phase 5 is complete when:

- A local k3d cluster runs the full platform stack.
- Flux reconciles the local channel from this repository.
- SOPS+age bootstraps only the secrets needed to start runtime secret
  management.
- Infisical owns runtime secrets and syncs them through the Operator.
- MinIO provides the local S3-compatible object store.
- cert-manager issues local TLS through step-ca.
- Local DNS resolves the platform hostnames.
- Crossplane is installed and the accepted local app-target model reconciles.
- Cluster security policies are enforced.
- Container images build, load locally, and have a remote registry contract.
- Buildkite local agent runs the same pipeline used remotely.
- Kong routes local traffic over local TLS.
- CloudNativePG runs Postgres and Atlas migrations locally.
- Backup and restore pass against local MinIO.
- API and Discord workloads run locally, with the bot using the beta guild.
- Authentik, OPAL/Cedar, and Pomerium protect local routes.
- Access policy, break-glass, service identity, and tenant/channel isolation
  are documented and tested locally.
- Observability collects metrics, logs, traces, dashboards, and alerts locally.

Remote channel onboarding after Phase 5 must be a channel configuration plus
credential supply problem, not a re-architecture.

## Superseded Main-Path Work

| Work | Reference | Disposition |
| --- | --- | --- |
| INIT-008 Platform Bootstrap | `feat/init-008-platform-bootstrap` at `9f7090f` | Reference only; VKE substrate discarded |
| INIT-009 GitOps Substrate | `feat/init-009-gitops-substrate` at `027b3b6` | Reference only; Flux/Kustomize/SOPS ideas salvaged through INIT-102 |
| INIT-017 Crossplane | `feat/init-017-crossplane` at `027b3b6` plus dirty pipeline artifacts | Paused and redone as INIT-106 |

## Source Authority

The full rationale, component table, channel schema sketch, audit-row
crosswalk, and D8 supersession draft live in `.pipeline/replan.md`.
