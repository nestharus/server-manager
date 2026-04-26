# Infrastructure

OpenTofu-managed infrastructure for the Humility platform.

## Structure

    infra/
    ├── bootstrap/
    │   └── state-backend/    # One-time: create Object Storage for tfstate
    ├── channels/
    │   ├── local.yaml        # Local k3d channel declaration
    │   └── dev.yaml          # Vultr VM k3s channel declaration
    ├── schemas/              # Platform channel JSON schemas
    ├── scripts/              # Channel resolution and validation tools
    ├── modules/
    │   └── platform-network/ # Shared VPC module
    └── tests/

## Bootstrap

1. Create the remote-state bucket:
   `cd infra/bootstrap/state-backend`
   `tofu init`
   `tofu apply -var="object_storage_cluster_id=<cluster-id>" -var="object_storage_tier_id=<tier-id>"`

2. Capture the `s3_hostname` output for later channel-root backend
   generation.

3. Validate channel definitions:
   `python infra/scripts/validate_platform_channels.py`

## Notes

- `local` is the local k3d target for first deployment work.
- `dev` is the remote Vultr VM k3s channel declaration.
- Later INIT-101 slices add channel roots, k3d bring-up, and Vultr VM
  plan surfaces.
