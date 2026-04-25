# Infrastructure

OpenTofu-managed Vultr infrastructure for the Humility platform.

## Prerequisites

- OpenTofu CLI `1.11.5` for INIT-008 verification. Roots keep
  `required_version = ">= 1.8.0"` as the feature floor.
- Python `>=3.10` for the channel resolver and generator scripts.
- Python packages: `jsonschema` and `PyYAML`.

## Structure

Current SLICE-025 state still contains the pre-channel roots. The intended
future-state layout, as of after SLICE-029, is:

    infra/
    ├── bootstrap/
    │   └── state-backend/       # Local-state Object Storage subscription handoff
    ├── channels/
    │   ├── dev.yaml             # First active platform channel
    │   └── fixtures/            # Resolver/spawn validation fixtures only
    ├── modules/
    │   ├── platform-network/    # Shared VPC module
    │   └── platform-cluster/    # Shared VKE module
    ├── roots/
    │   └── channels/
    │       └── dev/             # First active per-channel OpenTofu root
    ├── schemas/                 # Source and resolved channel contracts
    ├── scripts/                 # Channel resolver/generator validation tools
    └── templates/
        └── platform-channel/    # Parameterized root module

## Local Validation

SLICE-025 does not create channel files or roots yet. The active verification
surface remains the checked-in harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

Later INIT-008 slices move validation to `infra/roots/channels/dev/` and keep
the baseline local-only:

```bash
cd infra/bootstrap/state-backend
tofu init -backend=false
tofu validate

cd infra/roots/channels/dev
tofu init -backend=false
tofu validate
```

## Bootstrap Handoff

The bootstrap root is a local-state handoff point for Vultr Object Storage
subscription material. INIT-008 does not run `tofu apply` as verification.

1. Inspect or validate the bootstrap root locally:
   `cd infra/bootstrap/state-backend`
   `tofu init -backend=false`
   `tofu validate`

2. If an operator later performs an out-of-scope bootstrap apply, capture the
   sensitive handoff outputs locally and verify bucket `humility-tfstate`
   exists in the Object Storage subscription.

3. Initialize a channel root only after the later channel-root slices land:
   `cd infra/roots/channels/<id>`
   `tofu init -backend-config=backend.tfbackend`
   `tofu validate`

## Notes

- `dev` is the first ratified platform channel for fast iteration.
- `customer`, `internal`, and named ephemeral channels are deferred to a
  separate initiative opened after Phase 5 converges.
- All roots pin OpenTofu `>= 1.8.0` and Vultr provider `~> 2.30`.
- Channel roots live under `infra/roots/channels/<id>/`; hard
  dev/staging/production roots are retired by the channel pivot.
