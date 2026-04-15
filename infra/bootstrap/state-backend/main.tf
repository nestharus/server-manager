# One-time bootstrap: create the Vultr Object Storage bucket for tfstate.
# This root uses local state only. Run once, then never touch again.
#
# Usage:
#   cd infra/bootstrap/state-backend
#   tofu init
#   tofu apply \
#     -var="object_storage_cluster_id=<cluster-id>" \
#     -var="object_storage_tier_id=<tier-id>"

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.30"
    }
  }
}

variable "object_storage_cluster_id" {
  description = "Vultr object-storage cluster ID for the state backend."
  type        = number
}

variable "object_storage_tier_id" {
  description = "Vultr object-storage plan/tier ID."
  type        = number
}

variable "object_storage_label" {
  description = "Label for the object-storage subscription."
  type        = string
  default     = "humility-tfstate"
}

variable "bucket_name" {
  description = "Bucket name used for OpenTofu remote state."
  type        = string
  default     = "humility-tfstate"
}

provider "vultr" {}

resource "vultr_object_storage" "state" {
  cluster_id = var.object_storage_cluster_id
  tier_id    = var.object_storage_tier_id
  label      = var.object_storage_label
}

resource "vultr_object_storage_bucket" "tfstate" {
  object_storage_id = vultr_object_storage.state.id
  name              = var.bucket_name
  enable_versioning = true
}

output "bucket_name" {
  value = vultr_object_storage_bucket.tfstate.name
}

output "s3_hostname" {
  value = vultr_object_storage.state.s3_hostname
}

output "s3_access_key" {
  value     = vultr_object_storage.state.s3_access_key
  sensitive = true
}

output "s3_secret_key" {
  value     = vultr_object_storage.state.s3_secret_key
  sensitive = true
}
