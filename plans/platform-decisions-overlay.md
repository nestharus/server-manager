# Platform decisions overlay

Corrections and updates to `unified-platform-index.md` based on user
decisions and research results that landed after the merge.

## Auth stack — LOCKED (user confirmed)

| Concern | Decision | Source |
|---|---|---|
| Identity | **Authentik** (not Logto) | User: "Authentik is still a very good auth tool" |
| Authorization | **OPAL/Cedar** (not Casbin) | User: "we definitely want opal/cedar over casbin for our needs" |
| Proxy | **Pomerium** | User: "we definitely want Pomerium since we are running on k8s and behind a VPC" |
| Ephemeral certs | **Smallstep only if full PKI needed** | Research: Pomerium now handles SSH certs. Smallstep stays only for workload mTLS, cert-manager, ACME. |
| RLS pagination | **Logto may serve a specialized role** | User: "Logto has a different thing specifically for RLS paginated filtering" — research pending |

Conflict C6 from the merge is resolved: **OPAL/Cedar wins.**

## Hosting — OPEN (research completed, user decides)

From `plans/research/hetzner-vs-vultr.md`:

| Factor | Vultr | Hetzner |
|---|---|---|
| Managed K8s | ✅ VKE (free control plane) | ❌ Self-managed only |
| Managed Postgres | ✅ Yes | ❌ No |
| Cheaper compute | $5 for 1vCPU/1GB | €5.99 for 2vCPU/2GB (2x resources) |
| Object storage | $18/mo for 1TB | €7.72/mo for 1TB |
| OpenTofu provider | Broad (VKE, DB, S3, LB, VPC) | Core infra only (no managed K8s/DB) |
| Ops burden | Lower (managed services) | Higher (self-manage everything) |

**User decision needed**: Vultr has less ops burden (managed K8s + DB). Hetzner has cheaper compute but requires self-managing K8s control plane, Postgres, etc.

## CI/CD — LOCKED

From `plans/research/buildkite-capabilities.md`:

- **Buildkite replaces Dagger** for CI execution
- **Flux replaces Argo** for GitOps reconciliation
- **The Kafka+Debezium+Redis pipeline from the GitOps spec is NOT needed for Phase 1-2.** It's an optional Phase 7 addition only if Buildkite+Flux prove insufficient for dynamic environments.
- Conflict C10 resolved: custom build/event plane is **deferred, not default**

## S3 — CONDITIONAL ON HOSTING

From `plans/research/self-hosted-s3.md`:

- If Vultr: **Vultr Object Storage** (provider-native, simplest)
- If Hetzner: **Hetzner Object Storage** (cheaper, narrower features)
- Self-hosted fallback: **SeaweedFS** (best license + K8s balance)
- Don't self-host unless required

## IaC — LOCKED

- **OpenTofu** (not Terraform, not Crossplane)
- Conflict C2 resolved
- Conflict C7 resolved: **Crossplane dropped unless dynamic env research proves it necessary**

## Pomerium + Smallstep — RESOLVED

From `plans/research/pomerium-smallstep.md`:

- **Keep Pomerium** — identity-aware proxy, SSH access (2026 capability)
- **Keep Smallstep only if full PKI substrate needed** — workload mTLS beyond Pomerium, cert-manager, ACME
- If Auth v5's Smallstep was mainly for SSH → Pomerium covers it now
- User said they THINK they want Smallstep → research says conditional

## Phased plan updates

Phase 7 (Advanced Build/Event Control Plane) should be marked
**conditional** — only built if Buildkite+Flux prove insufficient.
Research says most of the custom Kafka pipeline can be eliminated.

Phase 3 auth components update:
- Authentik (confirmed)
- Pomerium (confirmed)
- OPAL/Cedar (confirmed, replaces C6 "needs research")
- Smallstep (conditional on PKI need)
