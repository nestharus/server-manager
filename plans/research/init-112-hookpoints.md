# INIT-112 Hookpoints

## Channel Schema

- `infra/schemas/platform-channel.schema.json`
- `infra/schemas/platform-channel-resolved.schema.json`
- `infra/channels/local.yaml`
- `infra/channels/dev.yaml`
- `infra/scripts/resolve_platform_channel.py` needs no logic change because
  backup has no derived defaults.

## Object Storage

- `gitops/channels/local/object-storage/buckets/job.yaml`
- `gitops/channels/local/object-storage/buckets/kustomization.yaml`
- Existing bucket bootstrap pattern remains in `minio-system`.

## CNPG Data Plane

- `gitops/channels/local/data-plane/sample-app/backup-credentials-infisicalsecret.yaml`
- `gitops/channels/local/data-plane/sample-app/cluster.yaml`
- `gitops/channels/local/data-plane/sample-app/kustomization.yaml`
- New `ScheduledBackup` manifest should live beside the sample Cluster because
  it targets that CNPG cluster.

## Verification

- Extend `infra/tests/validate_data_plane_local.sh` for the top-level backup
  contract.
- Add `infra/tests/validate_backup_dr_local.sh` for INIT-112 static/runtime
  proof.
- Add `infra/scripts/run-cnpg-restore-drill.sh` for deterministic runtime
  restore.
- Add `infra/scripts/snapshot-k3d-volumes.sh` for local control-cluster Docker
  volume snapshots.
- Add focused Python contract tests under `infra/tests`.

## Docs

- Update `infra/README.md` with Backup / DR commands.
- Add `docs/init-113-backup-dr-handoff.md` for the next slice.
