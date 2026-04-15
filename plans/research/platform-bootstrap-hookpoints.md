# Hookpoint Research: Platform Bootstrap Implementation

## Purpose

Documents what existing code, infrastructure, and decisions the
Platform Bootstrap implementation (P0645-P0649) touches or depends on.
This is a greenfield `infra/` tree after a full wipe of the prior flat
layout — hookpoints are primarily decision-level and forward-looking.

## Hookpoint 1 — State backend choice locked to Vultr Object Storage

**Source**: `plans/proposals/platform-bootstrap.md` §3 "Object-storage
state backing"; `plans/platform-decisions-overlay.md` "Self-hosted S3
alternatives" row.

**Constraint**: Provider-native `Vultr Object Storage` is the locked
state-backing choice. No self-hosted S3 layer (`SeaweedFS`, `MinIO`)
may appear in the bootstrap path. `infra/bootstrap/state-backend/main.tf`
implements this by provisioning a `vultr_object_storage` subscription
and `vultr_object_storage_bucket` with versioning enabled.

**Risk if violated**: Introducing a self-hosted storage dependency
into bootstrap creates a circular dependency — the cluster that would
host the storage doesn't exist yet during bootstrap.

## Hookpoint 2 — Module composition pattern for environment roots

**Source**: Proposal §3 "OpenTofu ownership model" — shared module
layer for reusable Vultr components, one OpenTofu root per platform
environment.

**Constraint**: `infra/modules/platform-network/` and
`infra/modules/platform-cluster/` are shared modules consumed by
per-environment roots (`infra/environments/dev/main.tf`). Future
environments (staging, production) must compose the same modules with
environment-specific variables. The modules must not contain
environment-specific hardcoded values.

**Files**: `infra/modules/platform-network/main.tf`,
`infra/modules/platform-cluster/main.tf`,
`infra/environments/dev/main.tf`.

## Hookpoint 3 — Flux CD GitOps layer (future consumer)

**Source**: Proposal §3 "Bootstrap handoff to GitOps"; decisions overlay
confirms `Flux CD` replaces `Argo CD`.

**Constraint**: The VKE clusters provisioned by Platform Bootstrap will
eventually be targeted by Flux reconciliation in a subsequent GitOps
Foundation initiative. The cluster module exposes `endpoint` and
`kube_config` (sensitive) outputs as the handoff seam. The GitOps
Foundation initiative will consume these outputs to bootstrap Flux
against the cluster.

**Implication**: The cluster module's output interface is a contract.
Renaming or removing `endpoint` or `kube_config` outputs would break
the GitOps handoff seam.

## Hookpoint 4 — State bootstrapping ordering

**Source**: Implementation pattern in `infra/bootstrap/state-backend/`
(local state) vs `infra/environments/dev/` (S3 backend).

**Constraint**: `infra/bootstrap/state-backend/` must be applied first
because it creates the Vultr Object Storage bucket that environment
roots use as their S3 backend. The dev environment root's
`backend.tfbackend` contains `REPLACE_AFTER_BOOTSTRAP` as the endpoint
placeholder, making this ordering explicit.

**Sequence**:
1. `tofu init && tofu apply` in `infra/bootstrap/state-backend/`
2. Capture `s3_hostname` output
3. Replace `REPLACE_AFTER_BOOTSTRAP` in `backend.tfbackend` with actual endpoint
4. `tofu init -backend-config=backend.tfbackend && tofu apply` in `infra/environments/dev/`

**Risk if violated**: Running the environment root before bootstrap
will fail on backend initialization because the S3 endpoint doesn't
exist yet.

## Hookpoint 5 — Two-tier cluster model preserved

**Source**: Proposal §3 "Platform shape" — platform cluster is the
control substrate, application clusters provisioned separately.

**Constraint**: The `platform-cluster` module provisions only the
platform/control cluster. Application clusters are owned by the
separate Application Cluster Provisioning initiative (which will use
Crossplane XRDs). The module must not be extended to provision
application workload clusters.

**Reference**: `plans/risk/platform-bootstrap-scope.md`,
`plans/risk/app-cluster-provisioning-scope.md`.

## Hookpoint 6 — Provider version pinning

**Source**: `infra/bootstrap/state-backend/main.tf` line 17,
`infra/environments/dev/main.tf` line 8.

**Constraint**: Vultr provider pinned to `~> 2.30` across all roots.
OpenTofu required version `>= 1.8.0`. These pins must stay consistent
across all roots and modules to prevent provider-version drift between
bootstrap and environment layers.

## Summary

The Platform Bootstrap implementation is greenfield infrastructure
after a wipe, but it hooks into:
- Locked architectural decisions (Vultr, Object Storage, two-tier model)
- A forward contract with GitOps Foundation (cluster outputs)
- A strict ordering dependency (state-backend before environment roots)
- Provider version consistency across all roots
