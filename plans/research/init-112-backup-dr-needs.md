# INIT-112 Needs Synthesis: Backup / DR

## Humility Context

The platform needs a local-first proof that a database can be backed up to
object storage and restored into a fresh cluster before application workloads
start depending on the data plane.

The useful confidence boundary is:

- local MinIO has a dedicated backup bucket;
- CNPG creates a scheduled backup against that bucket;
- a deterministic manual backup lands in MinIO;
- a restore drill creates a fresh cluster from object storage;
- schema and inserted data survive the restore.

## Contract Needs

The channel schema needs an optional top-level `backup` block because backup/DR
is shared platform infrastructure, not a property of a specific application
database. The block must include provider, endpoint, region, bucket,
destination path, retention, schedule, credentials Secret target, and
Infisical source path.

Local uses MinIO and bucket `humility-local-backups`. Remote `dev` records the
Vultr Object Storage endpoint and bucket name as a contract, with no bucket
creation.

## Operational Needs

The restore drill should be a script under `infra/scripts` and a harness under
`infra/tests`, matching prior INIT slices. It should be idempotent, clean up the
transient restore cluster by default, and leave the backup object available as
proof.

The local control cluster also needs a Docker-volume snapshot script for k3d so
operators have a coarse control-plane recovery artifact independent of CNPG
database backups.

## Gaps

Remote credentials and bucket creation remain later deployment work. The dev
channel can carry the provider contract, but INIT-112 must not try to create the
Vultr bucket.
