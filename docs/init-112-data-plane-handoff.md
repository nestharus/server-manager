# INIT-112 Handoff: Database Backups and Restore

INIT-111 established the app database data plane.

## Owned by INIT-111

- CloudNativePG operator raw manifest:
  `gitops/channels/local/data-plane/cnpg/rendered/cnpg-1.29.0.yaml`
- Atlas Operator raw render:
  `gitops/channels/local/data-plane/atlas/rendered/atlas-operator-0.7.28.yaml`
- Sample database namespace: `sample-app-db`
- Sample cluster: `Cluster/sample-app-postgres`
- Sample app database/user: `sample_app`
- Atlas migration: `AtlasMigration/sample-app`
- Migration directory: `database/migrations/sample-app`
- Database credential source:
  Infisical project `platform-databases`, environment `local`, path
  `/postgres/local/sample-app`
- Backup target config:
  `s3://humility-local-sample/cnpg/local/sample-app-postgres` through INIT-104
  MinIO

## Proof Harness

Run static validation:

```bash
infra/tests/validate_data_plane_local.sh --static-only
```

Run runtime validation after local Flux reconciliation:

```bash
infra/tests/validate_data_plane_local.sh
```

The runtime proof checks:

- `Deployment/cnpg-controller-manager` Available
- `Deployment/atlas-operator` Available
- database and backup credentials synced by Infisical
- `Cluster/sample-app-postgres` Ready=True
- `AtlasMigration/sample-app` Ready=True
- `psql` connects with the app URL Secret
- `sample_app.widgets` exists

## INIT-112 Scope Boundary

INIT-112 should add scheduled backups and restore proof. It should not redefine
the CNPG install path, database credential path, sample cluster name, or Atlas
migration mechanism.

The expected INIT-112 deliverables are:

- `ScheduledBackup` resource or equivalent CNPG backup schedule for
  `sample-app-postgres`
- backup completion proof against the existing MinIO destination
- restore drill into a separate recovery cluster
- verification that restored data and credentials behave as expected
- retention and failure-observability notes

Keep backup credentials in Infisical. Do not move database or object-storage
credentials into SOPS.
