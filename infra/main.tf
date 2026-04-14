terraform {
  required_version = ">= 1.8.0" # use_lockfile requires 1.8+

  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.21"
    }
  }

  # Remote state in Vultr Object Storage (S3-compatible).
  # Credentials come from backend config / standard AWS env vars.
  backend "s3" {
    region = "ewr"

    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    use_lockfile                = true
  }
}

provider "vultr" {
  api_key = var.vultr_api_key
}
