# INIT-111 Research: Data Plane

## Scope

INIT-111 adds the first application database data plane. It installs
CloudNativePG as the PostgreSQL operator, creates one sample application
PostgreSQL cluster, stores database credentials in Infisical, applies one
versioned Atlas migration, and proves local connectivity with `psql`.

This database plane is separate from Infisical's bundled PostgreSQL. The
Infisical database remains an implementation detail of INIT-103's secret
service. INIT-111 owns app-facing databases only.

## CloudNativePG Shape

CloudNativePG 1.29.0 is the current GA minor line as of 2026-04-26. Its direct
install path is a raw Kubernetes manifest from the upstream release branch. The
operator installs into `cnpg-system` as `Deployment/cnpg-controller-manager`.

The sample cluster should use the `postgresql.cnpg.io/v1` `Cluster` API with:

- `instances: 1` for local proof;
- `bootstrap.initdb.database` and `bootstrap.initdb.owner` for the sample app
  database and owner;
- an application credential Secret sourced from Infisical;
- a small local PVC for storage;
- `backup.barmanObjectStore` pointed at INIT-104 MinIO as config-only. INIT-112
  owns scheduled `Backup` resources and restore drills.

## Atlas Shape

Atlas Operator chart `0.7.28` installs CRDs for `AtlasMigration`. The operator
supports versioned migrations from a Kubernetes `ConfigMap`; the
`AtlasMigration` resource references the migration directory and a database URL
from a Secret. This matches local GitOps and keeps schema versions in the
repository.

INIT-111 uses the versioned migration flow, not declarative schema apply, so the
repo carries ordered SQL migration files plus `atlas.sum`.

## Infisical Credential Flow

The source of truth for app database credentials is the Infisical project
`platform-databases`, environment `local`, path `/postgres/local/sample-app`.
The local bootstrap script creates or finds that project/path, seeds:

- `username`
- `password`
- `database`
- `host`
- `port`
- `url`

Kubernetes receives those values through `InfisicalSecret` resources. No app DB
credential is stored in SOPS or committed as a Kubernetes Secret.

## Local Proof

A valid local proof needs all of these:

- `Cluster/sample-app-postgres` reports `Ready=True`;
- `AtlasMigration/sample-app` reports `Ready=True`;
- a `psql` connection using the synced app credentials succeeds;
- the sample table from the migration exists.

## Source Links

- CloudNativePG install docs:
  `https://cloudnative-pg.io/docs/1.29/installation_upgrade/`
- CloudNativePG 1.29 release:
  `https://cloudnative-pg.io/releases/cloudnative-pg-1-29.0-released/`
- Atlas Operator versioned migrations:
  `https://atlasgo.io/integrations/kubernetes/versioned`
