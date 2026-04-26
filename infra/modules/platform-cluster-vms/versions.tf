terraform {
  required_version = ">= 1.8.0"

  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}
