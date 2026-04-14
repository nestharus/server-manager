terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Hetzner Object Storage is S3-compatible. Keep only environment-
  # independent backend settings here and pass bucket/key/endpoints via
  # `tofu init -backend-config=environments/<env>/backend.tfbackend`.
  backend "s3" {
    region = "fsn1"

    force_path_style            = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}

provider "hcloud" {
  token = var.hcloud_token
}
