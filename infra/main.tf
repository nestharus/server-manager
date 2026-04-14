terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Hetzner Object Storage is S3-compatible, so the standard s3 backend works
  # here. Keep concrete bucket keys and credentials outside source and pass them
  # during `tofu init` with environment-specific backend config.
  backend "s3" {
    bucket = "humility-terraform-state"
    key    = "humility/ENVIRONMENT/terraform.tfstate"
    region = "fsn1"

    endpoint = "https://fsn1.your-objectstorage.com"

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
