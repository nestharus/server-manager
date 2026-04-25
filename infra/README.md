# Infrastructure

OpenTofu-managed Vultr infrastructure for the Humility platform.

## Prerequisites

- OpenTofu CLI `1.11.5` for INIT-008 verification. Roots keep
  `required_version = ">= 1.8.0"` as the feature floor.
- Python `>=3.10` for the channel resolver and generator scripts.
- `jsonschema` any `4.x`.
- `PyYAML` any `6.x`.

## Structure

Current SLICE-026 state introduces the channel registry contract while keeping
the old environment roots temporarily intact for SLICE-027 deletion.

    infra/schemas/
      platform-channel.schema.json
      platform-channel-resolved.schema.json

Source and resolved JSON Schemas for platform channel files. The source schema
validates checked-in YAML. The resolved schema validates the inherited JSON that
later generators and OpenTofu roots consume.

    infra/channels/<id>.yaml

Active channel declarations. `dev.yaml` is the only active channel in INIT-008.

    infra/channels/fixtures/

Resolver and spawner fixtures. These are test material only and are not shipped
as active platform channels.

    infra/scripts/

Local-only channel tooling:

- `resolve_platform_channel.py` resolves a channel and validates the result.
- `spawn_platform_channel.py` writes an ephemeral child channel under `.tmp/`.
- `validate_platform_channels.py` validates the active registry and fixtures.

    infra/roots/channels/<id>/

Per-channel OpenTofu roots. These are created in SLICE-027.

    infra/environments/{dev,staging,production}/

The old hard environment roots still exist during SLICE-026 so the existing
OpenTofu validation harness remains green. They are deleted in SLICE-027 after
the `infra/roots/channels/dev/` replacement lands.

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
