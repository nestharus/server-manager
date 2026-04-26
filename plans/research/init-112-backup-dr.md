# INIT-112 Research: Backup / DR

## Question

How should the platform add database backup and restore proof after INIT-111
without widening into application-level backup policy or remote bucket
provisioning?

## Findings

INIT-111 already installs CloudNativePG 1.29.0, configures the sample cluster
with Barman object-store settings, and syncs object-store credentials through
Infisical. Its handoff explicitly excludes `ScheduledBackup`, restore drill, and
durability acceptance.

INIT-104 already owns local MinIO, the `minio-root` InfisicalSecret in
`minio-system`, a bucket bootstrap Job pattern, and runtime S3 proof through
`mc`. The backup bucket can reuse that pattern without adding a controller or
Helm release.

CNPG 1.29 exposes `ScheduledBackup` and `Backup` CRDs in the raw operator
manifest already committed under `gitops/channels/local/data-plane/cnpg`. The
schedule format includes seconds. A `ScheduledBackup` can trigger an immediate
first run, while a manual `Backup` resource is better for deterministic restore
drills because the script can name it, wait for completion, and restore the
latest Barman backup. The CNPG operand image must include `barman-cloud-*`; for
INIT-112 that means using the CNPG `system` image until the Barman Cloud CNPG-I
plugin migration is implemented.

Restore proof should create a fresh transient CNPG `Cluster` with
`bootstrap.recovery.source` and an `externalClusters[].barmanObjectStore`
definition pointing at the source cluster backup path. The proof must verify a
known schema and known inserted row, not only cluster readiness.

The existing `data_plane.backup` field makes backups look like a sample database
subfield. INIT-112 is platform backup/DR, so a top-level optional `backup` block
is the correct channel contract. Local should set it to MinIO, and remote `dev`
should record the Vultr Object Storage contract only. Crossplane bucket
creation for Vultr is not in scope.

## Non-Goals

- Application-level exports, per-app retention tiers, or app-owned restore
  procedures.
- Automatic Vultr Object Storage bucket creation.
- CNPG 1.30 plugin migration.
- Helm controller installation.
