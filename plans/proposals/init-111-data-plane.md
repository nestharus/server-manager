# INIT-111 Proposal: Data Plane with CloudNativePG and Atlas

## 1. Summary

INIT-111 adds an application PostgreSQL data plane. It extends the channel
contract with an optional `data_plane` block, installs CloudNativePG and Atlas
Operator from raw manifests, creates one sample CloudNativePG cluster, syncs app
database credentials from Infisical, applies one versioned Atlas migration, and
ships a local validation harness.

The work is eight implementation slices:

1. Pipeline artifacts.
2. Channel `data_plane` contract.
3. CloudNativePG raw operator manifests.
4. Sample PostgreSQL cluster, InfisicalSecret credentials, and MinIO backup
   target config.
5. Atlas Operator raw manifests and versioned migration resources.
6. Infisical database credential bootstrap.
7. Local validation harness and CI wiring.
8. Handoff and review artifacts.

## 2. Architecture

CloudNativePG runs in `cnpg-system`. The sample application database runs in
`sample-app-db` as `Cluster/sample-app-postgres` with one instance for local
proof. The cluster bootstraps `sample_app` and owner `sample_app` from a Secret
synced by the Infisical Operator.

Atlas Operator runs in `atlas-operator`. Its `AtlasMigration/sample-app`
resource reads the app database URL from an Infisical-synced Secret and reads
the versioned migration directory from a ConfigMap generated from
`database/migrations/sample-app`.

The CNPG `backup.barmanObjectStore` block points at INIT-104 MinIO using the
existing `Secret/minio-root`. INIT-111 only configures the target; INIT-112 owns
scheduled backups, restore, and durability acceptance.

## 3. Contracts

The channel `data_plane` block contains:

- provider and namespace fields for CNPG;
- the CNPG operator version and raw manifest path;
- sample app cluster name, namespace, database, owner, service, and storage;
- Infisical project/environment/path for database credentials;
- Atlas Operator chart/version/render path;
- Atlas migration name and repo migration directory;
- backup target provider, bucket, endpoint, region, and credential Secret.

## 4. Anti-Scope

INIT-111 does not schedule backups, test restores, create app workloads, expose
a database UI, provision remote database runtime credentials, replace
Infisical's bundled PostgreSQL, or introduce Helm controller resources.

## 5. Risk Notes

The main shortcut risk is stopping at rendered manifests without a real
database proof. The harness waits for CNPG, the cluster, Atlas migration
status, a real `psql` connection, and the migrated table.

The second risk is leaking credentials into Git. The proposal uses Infisical as
the source of truth and scans for database password literals.

The third risk is backup overreach. The cluster carries object-store
configuration only. No `ScheduledBackup` or restore resource ships here.

## 6. Acceptance

- local and dev channels resolve with `data_plane`;
- `kubectl kustomize gitops/channels/local/data-plane` succeeds;
- `kubectl kustomize gitops/channels/local` succeeds;
- static harness passes without a cluster;
- runtime harness proves CNPG cluster Ready, Atlas migration Ready, `psql`
  connect, and `sample_app.widgets` exists;
- CodeRabbit and PR review artifacts are clean or residual gaps are recorded.
