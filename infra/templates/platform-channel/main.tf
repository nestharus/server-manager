module "network" {
  source         = "../../modules/platform-network"
  environment    = var.channel_id
  region         = var.region
  v4_subnet      = var.vpc_v4_subnet
  v4_subnet_mask = var.vpc_v4_subnet_mask
}

module "cluster" {
  source             = "../../modules/platform-cluster"
  environment        = var.channel_id
  region             = var.region
  cluster_label      = var.cluster_label
  kubernetes_version = var.cluster_kubernetes_version
  vpc_id             = module.network.vpc_id
  node_plan          = var.node_plan
  node_quantity      = var.node_quantity
  ha_controlplanes   = var.ha_controlplanes
  enable_firewall    = var.enable_firewall
}
