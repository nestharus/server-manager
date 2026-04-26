# INIT-112 Handoff: Database Backups and Restore

INIT-111 established the app database data plane.

## Owned by INIT-111

- CloudNativePG operator raw manifest:
  `gitops/channels/local/data-plane/cnpg/rendered/cnpg-1.29.0.yaml`
- Atlas Operator raw render:
  `gitops/channels/local/data-plane/atlas/rendered/atlas-operator-0.7.28.yaml`
- Sample database namespace: `sample-app-db`
- Sample cluster: `Cluster/sample-app-postgres`
- Current INIT-112 operand image:
  `ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie`
- Sample app database/user: `sample_app`
- Atlas migration: `AtlasMigration/sample-app`
- Migration directory: `database/migrations/sample-app`
- Database credential source:
  Infisical project `platform-databases`, environment `local`, path
  `/postgres/local/sample-app`
- Initial backup target config, superseded by INIT-112's dedicated backup
  bucket:
  `s3://humility-local-backups/cnpg/local/sample-app-postgres` through INIT-104
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

## INIT-112 Completion

INIT-112 added scheduled backups and restore proof without redefining the CNPG
install path, database credential path, sample cluster name, or Atlas migration
mechanism.

Delivered INIT-112 artifacts:

- `ScheduledBackup` resource for
  `sample-app-postgres`
- backup completion proof against MinIO bucket `humility-local-backups`
- restore drill into a separate recovery cluster through
  `infra/scripts/run-cnpg-restore-drill.sh`
- verification that restored schema and inserted drill data behave as expected
- retention and failure-observability notes
- migration reminder from CNPG's deprecated in-tree Barman object-store backup
  fields to the Barman Cloud CNPG-I plugin before any CNPG 1.30 upgrade

Keep backup credentials in Infisical. Do not move database or object-storage
credentials into SOPS.
