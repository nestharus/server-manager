# Vultr Object Storage Bucket — Bug Fix Research

Date: 2026-04-15

## 1. What the current code does wrong

`infra/bootstrap/state-backend/main.tf` line 52 declares:

```hcl
resource "vultr_object_storage_bucket" "tfstate" {
  object_storage_id = vultr_object_storage.state.id
  name              = var.bucket_name
  enable_versioning = true
}
```

The `vultr_object_storage_bucket` resource **does not exist** in the Vultr Terraform
provider v2.30.1 (the version pinned by the `~> 2.30` constraint and locked in
`.terraform.lock.hcl`). Running `tofu init` or `tofu plan` will fail with an error
like:

```
Error: Invalid resource type
  "vultr_object_storage_bucket" is not a valid resource type for provider "vultr".
```

The outputs at lines 58-59 (`vultr_object_storage_bucket.tfstate.name`) also reference
this non-existent resource and will fail.

The test file `infra/tests/validate_platform_bootstrap.sh` (lines 198-199) asserts
that `vultr_object_storage_bucket` exists in the source, so the test will pass on
source content but the Terraform plan/apply will fail.

## 2. What actually exists in the Vultr provider

### v2.30.1 (latest released — March 4, 2026)

**Resources:**
- `vultr_object_storage` — creates an object storage subscription. Accepts
  `cluster_id` (int, required), `tier_id` (int, required), `label` (string, optional).
  Exports `s3_hostname`, `s3_access_key`, `s3_secret_key`, `date_created`, `location`,
  `region`, `status`. Does **not** manage buckets.

**Data sources:**
- `vultr_object_storage` — read existing object storage subscriptions
- `vultr_object_storage_cluster` — list available clusters
- `vultr_object_storage_tier` — list available tiers

No bucket resource or data source exists in any released version (v2.25.0 through
v2.30.1).

### master branch (unreleased — merged March 30, 2026)

The `master` branch **does** contain `vultr_object_storage_bucket` as part of a larger
organization/IAM merge (commit d64fdb9). This resource:

- Accepts: `object_storage_id` (string, required, ForceNew), `name` (string, required,
  ForceNew), `enable_versioning` (bool, optional), `enable_lock` (bool, optional)
- Exports: `date_created`
- Uses the Vultr API (`govultr/v3` SDK) to call `POST /v2/object-storages/{id}/buckets`

This matches the schema used in our `main.tf` almost exactly. The resource is real but
**not yet released**.

### Vultr REST API

The Vultr API v2 already exposes bucket management endpoints:
- `POST /v2/object-storages/{object-storage-id}/buckets` — create bucket
- `DELETE /v2/object-storages/{object-storage-id}/buckets/{bucket-name}` — delete bucket
- Lifecycle and archival endpoints also exist

The API-side support is live; only the Terraform provider release is lagging.

## 3. Fix options

### Option A: Wait for next provider release (recommended if timeline allows)

The `vultr_object_storage_bucket` resource is merged to `master` and will ship in the
next provider release (likely v2.31.0). When released:

1. Update the version constraint from `~> 2.30` to `~> 2.31` (or to a version that
   includes the bucket resource).
2. Update `.terraform.lock.hcl` via `tofu init -upgrade`.
3. The existing `main.tf` code will work as-is with no other changes.

**Pros:** Zero code changes to `main.tf` logic; uses the native provider resource;
matches how the code was clearly designed to work.
**Cons:** Blocks on an external release with no published timeline. The `~> 2.30`
constraint would need to become `~> 2.31` (minor semver bump), which is a one-line
change.

### Option B: Use the AWS provider with custom S3 endpoint

Add the `hashicorp/aws` provider configured to point at Vultr's S3-compatible endpoint,
and use `aws_s3_bucket` + `aws_s3_bucket_versioning` to create the bucket.

```hcl
provider "aws" {
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  region                      = "us-east-1"  # required but ignored by Vultr

  access_key = vultr_object_storage.state.s3_access_key
  secret_key = vultr_object_storage.state.s3_secret_key

  endpoints {
    s3 = "https://${vultr_object_storage.state.s3_hostname}"
  }
}

resource "aws_s3_bucket" "tfstate" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

**Pros:** Works today; well-established pattern for S3-compatible providers;
`aws_s3_bucket` is mature and battle-tested.
**Cons:** Pulls in the entire AWS provider (~400 MB) for one resource; adds a second
provider dependency to a bootstrap module; AWS provider may emit warnings or behave
unexpectedly with non-AWS S3 implementations; `skip_*` flags may change across AWS
provider versions.

### Option C: Use `terraform_data` / `null_resource` with local-exec

Create the bucket via a shell command after the object storage subscription is active.

```hcl
resource "terraform_data" "create_bucket" {
  depends_on = [vultr_object_storage.state]

  provisioner "local-exec" {
    command = <<-EOT
      aws s3 mb "s3://${var.bucket_name}" \
        --endpoint-url "https://${vultr_object_storage.state.s3_hostname}"
      aws s3api put-bucket-versioning \
        --bucket "${var.bucket_name}" \
        --versioning-configuration Status=Enabled \
        --endpoint-url "https://${vultr_object_storage.state.s3_hostname}"
    EOT
    environment = {
      AWS_ACCESS_KEY_ID     = vultr_object_storage.state.s3_access_key
      AWS_SECRET_ACCESS_KEY = vultr_object_storage.state.s3_secret_key
    }
  }
}
```

Alternatively, use `curl` against the Vultr API directly instead of the AWS CLI.

**Pros:** No additional provider dependencies; lightweight.
**Cons:** Requires `aws` CLI (or `curl` + API key) on the machine running `tofu apply`;
not idempotent (re-running will error if bucket exists unless guarded); bucket is not
in Terraform state so `tofu destroy` won't remove it; versioning enable may not be
supported by Vultr's S3 API.

### Option D: Remove bucket creation from Terraform entirely

Accept that the bootstrap module only creates the object storage subscription. Document
a manual (or scripted) post-apply step to create the bucket.

```hcl
# Remove lines 52-56 and the bucket_name output (lines 58-60).
# Add a note in the usage comment about creating the bucket manually.
```

**Pros:** Simple; no extra dependencies; avoids the provider version issue entirely.
**Cons:** Breaks the "single `tofu apply` bootstraps everything" design; requires a
separate step that must be documented and followed.

## 4. Recommendation

**Primary recommendation: Option A** — wait for the provider release and bump the
version constraint. The resource is already merged to `master`, the Vultr API support
is live, and the existing code matches the upcoming resource schema exactly. This is
the approach the code was designed for.

**If the bootstrap must work before the next provider release: Option B** (AWS provider
with custom endpoint) is the most robust interim fix. It keeps the bucket in Terraform
state, supports versioning natively, and is a well-known pattern. The cost is pulling
in the AWS provider.

**If pulling in the AWS provider is unacceptable: Option C** (local-exec) is a
pragmatic workaround, but must include idempotency guards and accept that the bucket
won't be in Terraform state.

**Not recommended: Option D** — it breaks the single-command bootstrap design that the
module comments describe.

## 5. Affected files

Any fix will need to touch:
- `infra/bootstrap/state-backend/main.tf` — the resource and outputs
- `infra/bootstrap/state-backend/.terraform.lock.hcl` — if provider version changes
- `infra/tests/validate_platform_bootstrap.sh` — assertions about resource names
  (lines 198-199) must match whatever resource type replaces `vultr_object_storage_bucket`

Downstream files that reference outputs (`s3_hostname`, `s3_access_key`, etc.) are
unaffected since those come from `vultr_object_storage.state`, not the bucket resource.
