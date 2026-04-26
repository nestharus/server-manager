# INIT-113 Handoff: Application Runtime After Backup / DR

INIT-112 established platform database Backup / DR for the INIT-111 data plane.

## Owned by INIT-112

- Top-level channel backup contract:
  `infra/channels/local.yaml` and `infra/channels/dev.yaml`
- Local backup bucket:
  `humility-local-backups`
- CNPG backup credentials Secret:
  `Secret/backup-object-storage` in `sample-app-db`, sourced from Infisical
  project `platform-storage`, environment `local`, path `/object-storage/local/`
- CNPG scheduled backup:
  `ScheduledBackup/sample-app-postgres-daily` in `sample-app-db`
- CNPG operand image:
  `ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie`, required by the
  native CNPG 1.29 Barman Cloud path
- Local retention policy:
  `7d`
- Restore drill:
  `infra/scripts/run-cnpg-restore-drill.sh`
- Backup / DR harness:
  `infra/tests/validate_backup_dr_local.sh`
- k3d volume snapshot script:
  `infra/scripts/snapshot-k3d-volumes.sh`

## Proof Commands

Static proof:

```bash
bash infra/tests/validate_backup_dr_local.sh --static-only
```

Runtime proof:

```bash
bash infra/tests/validate_backup_dr_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

The runtime proof creates a manual CNPG `Backup`, verifies backup objects under
`s3://humility-local-backups/cnpg/local/sample-app-postgres`, restores into a
fresh transient cluster, and verifies `sample_app.widgets` plus the inserted
drill row.

## INIT-113 Boundary

INIT-113 can assume that the platform has a recoverable PostgreSQL substrate.
It should not redefine CNPG installation, backup bucket creation, or restore
drill mechanics.

Application-level backups remain a per-application concern. If INIT-113 adds
application workloads, it should use the API/database contracts and leave
platform backup policy in the top-level channel `backup` block.

Remote Vultr Object Storage bucket creation is still out of scope until remote
deployment work creates provider resources.

Before any CNPG 1.30 upgrade, migrate backup execution to the Barman Cloud
CNPG-I plugin and move the operand image back off the deprecated `system`
variant.
