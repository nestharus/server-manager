# INIT-112 Proposal: Backup / DR

## Scope

INIT-112 adds platform database backup and restore proof for the INIT-111 data
plane.

Implementation slices:

1. Promote backup settings to a top-level optional channel `backup` block.
2. Configure local MinIO bucket `humility-local-backups` and dev Vultr Object
   Storage backup contract.
3. Sync CNPG backup credentials from Infisical into the sample database
   namespace.
4. Add CNPG `ScheduledBackup` for `sample-app-postgres` with 7d local
   retention and immediate first run.
5. Add a restore drill script that inserts known data, creates a manual backup,
   proves objects exist in MinIO, restores to a fresh CNPG cluster, and verifies
   schema plus data.
6. Add a k3d Docker-volume snapshot script for the local control cluster.
7. Add static/runtime harness coverage and handoff documentation for INIT-113.

## Design

`backup` is optional at the channel schema level. Local channels can set:

- `provider: minio`
- `endpoint: http://minio.minio-system.svc.cluster.local:9000`
- `bucket: humility-local-backups`
- `destination_path: s3://humility-local-backups/cnpg/local/sample-app-postgres`
- `retention_policy: 7d`
- `schedule: "0 0 0 * * *"`
- `credentials_secret_name: backup-object-storage`
- `credentials_secret_namespace: sample-app-db`
- Infisical source `platform-storage` `/object-storage/local/`

Remote dev records:

- `provider: vultr-object-storage`
- `endpoint: https://ewr1.vultrobjects.com`
- bucket `humility-dev-backups`
- matching Infisical source `/object-storage/dev/`

The sample CNPG Cluster uses the same backup object-store target. A
`ScheduledBackup` resource runs daily and creates its first backup immediately.
The deterministic restore proof uses a manual `Backup` CR so the harness does
not need to wait for the next scheduled window.

The CNPG PostgreSQL operand uses `ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie`
because CNPG 1.29 native Barman backup execution requires `barman-cloud-*`
commands inside the operand image. The pre-1.30 follow-up is to migrate to the
Barman Cloud CNPG-I plugin and then return to the non-system operand image.

## Anti-Scope

- No application-level backups.
- No Vultr bucket auto-creation.
- No Helm controller.
- No SOPS-managed backup credentials.
- No CNPG plugin migration before a CNPG 1.30 upgrade.

## Acceptance

- Channel resolver accepts local and dev backup blocks.
- Kustomize renders the backup bucket and `ScheduledBackup`.
- Local harness proves the scheduled backup exists, a manual backup completes,
  MinIO contains backup objects, and a fresh restore cluster contains
  `sample_app.widgets` plus the drill row.
- The k3d snapshot script can create local Docker-volume tar archives.
