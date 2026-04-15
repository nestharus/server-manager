# Staging environment — on-demand, ephemeral.
# Purpose: benchmarks, load tests at production-equivalent sizing.
# Spin up for release candidate validation, destroy after.

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
  environment    = "staging"
  region         = "ewr"
  v4_subnet      = "10.40.16.0"
  v4_subnet_mask = 20
}

module "cluster" {
  source             = "../../modules/platform-cluster"
  environment        = "staging"
  region             = "ewr"
  cluster_label      = "humility-staging-platform"
  kubernetes_version = "v1.32.3+1"
  vpc_id             = module.network.vpc_id
  node_plan          = "vc2-2c-4gb"
  node_quantity      = 3
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
