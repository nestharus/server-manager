# Infrastructure

OpenTofu-managed Vultr infrastructure for the Humility platform.

## Local prerequisites

- OpenTofu CLI `1.11.5` (the version INIT-008 acceptance was verified against;
  newer 1.x patch releases should also work, report drift if they do not).
- Python `3.12` or compatible.
- `jsonschema` any `4.x`.
- `PyYAML` any `6.x`.

## Structure

INIT-008 uses a channel registry plus one active `dev` channel root. The old
hard environment roots were retired by the channel pivot.

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

Per-channel OpenTofu roots. `infra/roots/channels/dev/` is the only active
channel root in INIT-008.

GitOps source for the control cluster lives in `gitops/`; see `gitops/README.md` for the Flux + SOPS + channel-overlay layout.

## Local verification

The active no-credential verification surface is the checked-in harness:

```bash
bash infra/tests/validate_platform_bootstrap.sh
```

The harness is the observable done-surface for INIT-008. It checks the
OpenTofu CLI version, recursive formatting, bootstrap and active channel root
validation, schema and channel fixture behavior, generated artifact drift,
absence of retired environment roots, provider lockfile presence, and absence
of committed credentials in `.tf`, `.tfbackend`, `.yaml`, and generated active
channel tfvars files.

```bash
cd infra/bootstrap/state-backend
tofu init -backend=false
tofu validate

cd infra/roots/channels/dev
tofu init -backend=false
tofu validate
```

## Provider-backed plan runbook (optional)

This path is optional. INIT-008 baseline verification works without Vultr or
Object Storage credentials; use the no-credential commands in
[Local verification](#local-verification) for the required acceptance surface.

Provider-backed planning reads current Vultr API state. It must not be followed
by `tofu apply` in INIT-008 scope. `tofu apply` is out-of-scope for Phase 5
entirely and belongs to a separate post-Phase-5 deployment initiative.

```bash
# Prerequisites:
#   - Vultr API key in env (VULTR_API_KEY)
#   - S3-compatible credentials for state backend (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
#     supplied as Vultr Object Storage S3 credentials
#   - Bucket "humility-tfstate" already created by operator (per
#     "State Backend Bounded Posture")

cd infra/roots/channels/dev

# Initialize against the committed backend config (provider-backed).
# Operator supplies the S3 endpoint via -backend-config flag, since the
# committed backend.tfbackend intentionally omits credentials and endpoint.
tofu init -backend-config=backend.tfbackend \
  -backend-config="endpoint=https://${OBJECT_STORAGE_HOSTNAME}" \
  -backend-config="access_key=${AWS_ACCESS_KEY_ID}" \
  -backend-config="secret_key=${AWS_SECRET_ACCESS_KEY}"

# Read-only plan against current Vultr API state.
tofu plan
```

## Bootstrap Handoff

The bootstrap root is a local-state handoff point for Vultr Object Storage
subscription material. It creates the Object Storage subscription only; it does
not create or manage an Object Storage bucket resource. INIT-008 verification
does not apply infrastructure.

1. Inspect or validate the bootstrap root locally:
   `cd infra/bootstrap/state-backend`
   `tofu init -backend=false`
   `tofu validate`

2. If an operator later performs an out-of-scope future deployment apply,
   capture the sensitive handoff outputs locally: `bucket_name`,
   `s3_hostname`, `s3_access_key`, and `s3_secret_key`.

3. Manually create bucket `humility-tfstate` inside the Object Storage
   subscription through the Vultr UI or aws-CLI-compatible tooling. Enable
   Object Storage versioning at bucket creation time so prior state versions
   are recoverable.

4. Confirm the bucket name in the resolved channel config matches the actual
   bucket before invoking backend initialization.

5. For the optional provider-backed `dev` plan path, initialize the channel
   root with operator-supplied endpoint and credentials using the runbook
   above.

The S3 endpoint is supplied at `tofu init` time through backend-config flags or
the operator's local environment. The channel schema does not carry endpoint
prose fields, and resolved channel JSON does not require a concrete endpoint.

## State Backend Bounded Posture

INIT-008 uses a single remote-state bucket, `humility-tfstate`, with
per-channel state keys at `channels/<id>/terraform.tfstate`. The active `dev`
key is `channels/dev/terraform.tfstate`.

INIT-008 does not claim distributed locking. The Vultr Object Storage backend's
S3-compatible locking is best-effort; for Phase 5 single-operator local
verification, locking is not load-bearing.

INIT-008 has no automated restore tooling. Operators can manually pull a prior
versioned state object if needed, relying on Object Storage versioning, the
operator-owned object-storage versioning setting enabled at bucket creation
time. The post-Phase-5 deployment initiative owns runbook-level restore tooling.

Bootstrap outputs `s3_access_key` and `s3_secret_key` are sensitive. The
operator captures them locally and supplies them through backend init flags or
environment variables. INIT-008 does not commit credentials; SOPS/age is
INIT-009's concern.

## Channel Retirement

Removing `infra/channels/<id>.yaml` retires the channel. The resolver refuses
to resolve a retired id, so a retired channel is no longer an active
OpenTofu target.

Per-channel roots such as `infra/roots/channels/<id>/` may remain or be
deleted; the harness handles both states. Remote state files for retired
channels are retained until an explicit operator cleanup. INIT-008 ships no
`cleanup-state` tooling; state-cleanup automation is post-Phase-5 deployment
scope.

## Notes

- `dev` is the first ratified platform channel for fast iteration.
- `customer`, `internal`, and named ephemeral channels are deferred to a
  separate initiative opened after Phase 5 converges.
- All roots pin OpenTofu `>= 1.8.0` and Vultr provider `~> 2.30`.
- Channel roots live under `infra/roots/channels/<id>/`; hard
  dev/staging/production roots are retired by the channel pivot.
