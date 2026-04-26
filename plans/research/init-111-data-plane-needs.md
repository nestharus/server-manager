# INIT-111 Synthesis: User Needs and Decisions

## Decisions

- D-CNPG-VERSION: install CloudNativePG `1.29.0` from the upstream raw release
  manifest.
- D-CNPG-NAMESPACE: run CNPG in `cnpg-system`.
- D-APP-NAMESPACE: run the sample app database in `sample-app-db`.
- D-SAMPLE-CLUSTER: create `Cluster/sample-app-postgres`.
- D-SAMPLE-DB: create database `sample_app` owned by `sample_app`.
- D-INFISICAL: store credentials in Infisical project `platform-databases`,
  environment `local`, path `/postgres/local/sample-app`.
- D-ATLAS: install Atlas Operator chart `0.7.28` as raw rendered manifests in
  `atlas-operator`.
- D-MIGRATIONS: store versioned Atlas migrations in repo and project them into
  the cluster as a ConfigMap.
- D-BACKUP-CONFIG: configure CNPG Barman object store against INIT-104 MinIO but
  do not create scheduled backups.
- D-PROOF: prove Ready cluster, Ready migration, `psql` connect, and schema
  verify locally.

## Humility Context

The platform already has local k3d, Flux, Infisical, MinIO, TLS/DNS,
Crossplane, security baseline, registry, Buildkite, and Kong. The next useful
substrate is a database plane that later app workloads can consume without
coupling themselves to Infisical's internal database.

The first implementation should be boring and observable: one operator, one
sample cluster, one migration, one validation harness. Backup scheduling,
restore drills, and app workloads are intentionally left to INIT-112 and
INIT-113.

## Gaps

Remote channel database credentials and object-store endpoints are contract
only in this slice. The local proof is complete; remote runtime bootstrap waits
for remote Flux/Infisical ownership in later platform work.
