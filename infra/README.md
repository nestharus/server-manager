# Infrastructure

OpenTofu-managed Vultr infrastructure for the Humility platform.

## Structure

    infra/
    ├── bootstrap/
    │   └── state-backend/    # One-time: create Object Storage for tfstate
    ├── modules/
    │   ├── platform-network/ # Shared VPC module
    │   └── platform-cluster/ # Shared VKE module
    └── environments/
        ├── dev/              # Persistent dev platform root
        ├── staging/          # On-demand validation root
        └── production/       # Persistent production root

## Bootstrap

1. Create the remote-state bucket:
   `cd infra/bootstrap/state-backend`
   `tofu init`
   `tofu apply -var="object_storage_cluster_id=<cluster-id>" -var="object_storage_tier_id=<tier-id>"`

2. Capture the `s3_hostname` output and replace `REPLACE_AFTER_BOOTSTRAP`
   in the target environment's `backend.tfbackend`.

3. Initialize and apply an environment root:
   `cd infra/environments/dev`
   `tofu init -backend-config=backend.tfbackend`
   `tofu apply`

## Notes

- `dev` is the always-on platform environment for fast iteration.
- `staging` uses production-equivalent sizing but is intended to be spun
  up only for release validation.
- `production` is the persistent user-facing environment.
- All roots pin OpenTofu `>= 1.8.0` and Vultr provider `~> 2.30`.
