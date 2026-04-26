locals {
  cluster_name = "humility-${var.channel_id}"
}

module "network" {
  source = "../../modules/platform-network"
  count  = var.cluster_target == "vultr-vms" ? 1 : 0

  channel        = var.channel_id
  region         = var.vultr_region
  v4_subnet      = var.vpc_v4_subnet
  v4_subnet_mask = var.vpc_v4_subnet_mask
}

module "cluster_k3d" {
  source = "../../modules/platform-cluster-k3d"
  count  = var.cluster_target == "k3d-local" ? 1 : 0

  channel_id      = var.channel_id
  cluster_name    = local.cluster_name
  k3s_version     = var.cluster_k3s_version
  servers         = var.k3d_servers
  agents          = var.k3d_agents
  registry_name   = var.k3d_registry_name
  registry_port   = var.k3d_registry_port
  kubeconfig_path = var.k3d_kubeconfig_path
}

module "cluster_vms" {
  source = "../../modules/platform-cluster-vms"
  count  = var.cluster_target == "vultr-vms" ? 1 : 0

  channel_id             = var.channel_id
  region                 = var.vultr_region
  vpc_id                 = var.cluster_target == "vultr-vms" ? module.network[0].vpc_id : ""
  k3s_version            = var.cluster_k3s_version
  server_count           = var.vultr_server_count
  server_plan            = var.vultr_server_plan
  agent_count            = var.vultr_agent_count
  agent_plan             = var.vultr_agent_plan
  ssh_key_ids            = var.vultr_ssh_key_ids
  allowed_ssh_cidrs      = var.vultr_allowed_ssh_cidrs
  remote_kubeconfig_path = var.vultr_remote_kubeconfig_path
  firewall_name          = var.vultr_firewall_name
}
