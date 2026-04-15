# Dev environment — persistent, always-on.
# Purpose: application dev, E2E tests, LLM video QA, fast iteration.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.30"
    }
  }

  backend "s3" {}
}

provider "vultr" {}

module "network" {
  source         = "../../modules/platform-network"
  environment    = "dev"
  region         = "ewr"
  v4_subnet      = "10.40.0.0"
  v4_subnet_mask = 20
}

module "cluster" {
  source             = "../../modules/platform-cluster"
  environment        = "dev"
  region             = "ewr"
  cluster_label      = "humility-dev-platform"
  kubernetes_version = "v1.32.3+1"
  vpc_id             = module.network.vpc_id
  node_plan          = "vc2-2c-4gb"
  node_quantity      = 2
  ha_controlplanes   = true
  enable_firewall    = true
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "cluster_id" {
  value = module.cluster.cluster_id
}

output "endpoint" {
  value = module.cluster.endpoint
}
