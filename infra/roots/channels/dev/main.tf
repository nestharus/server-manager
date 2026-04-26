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

module "platform_channel" {
  source = "../../../templates/platform-channel"

  channel_id                   = var.channel_id
  cluster_target               = var.cluster_target
  cluster_distribution         = var.cluster_distribution
  cluster_k3s_version          = var.cluster_k3s_version
  k3d_servers                  = var.k3d_servers
  k3d_agents                   = var.k3d_agents
  k3d_registry_name            = var.k3d_registry_name
  k3d_kubeconfig_path          = var.k3d_kubeconfig_path
  vpc_v4_subnet                = var.vpc_v4_subnet
  vpc_v4_subnet_mask           = var.vpc_v4_subnet_mask
  vultr_region                 = var.vultr_region
  vultr_server_count           = var.vultr_server_count
  vultr_server_plan            = var.vultr_server_plan
  vultr_agent_count            = var.vultr_agent_count
  vultr_agent_plan             = var.vultr_agent_plan
  vultr_ssh_key_ids            = var.vultr_ssh_key_ids
  vultr_allowed_ssh_cidrs      = var.vultr_allowed_ssh_cidrs
  vultr_remote_kubeconfig_path = var.vultr_remote_kubeconfig_path
  vultr_firewall_name          = var.vultr_firewall_name
}

variable "channel_id" {
  type        = string
  description = "Channel identifier from resolved channel JSON; no default; required"
}

variable "cluster_target" {
  type        = string
  description = "Cluster target from resolved channel JSON; no default; required"
}

variable "cluster_distribution" {
  type        = string
  description = "Cluster distribution from resolved channel JSON; no default; required"
}

variable "cluster_k3s_version" {
  type        = string
  description = "Pinned k3s version from resolved channel JSON; no default; required"
}

variable "k3d_servers" {
  type        = number
  default     = 1
  description = "Number of local k3d server nodes. Default: 1."
}

variable "k3d_agents" {
  type        = number
  default     = 1
  description = "Number of local k3d agent nodes. Default: 1."
}

variable "k3d_registry_name" {
  type        = string
  default     = "humility-local"
  description = "Local k3d registry name. Default: humility-local."
}

variable "k3d_kubeconfig_path" {
  type        = string
  default     = "~/.kube/humility-local.yaml"
  description = "Local kubeconfig output path. Default: ~/.kube/humility-local.yaml."
}

variable "vpc_v4_subnet" {
  type        = string
  default     = "10.40.0.0"
  description = "VPC IPv4 subnet from resolved channel JSON. Default: 10.40.0.0."
}

variable "vpc_v4_subnet_mask" {
  type        = number
  default     = 20
  description = "VPC IPv4 subnet mask from resolved channel JSON. Default: 20."
}

variable "vultr_region" {
  type        = string
  description = "Vultr region from resolved channel JSON; no default; required"
}

variable "vultr_server_count" {
  type        = number
  description = "Vultr k3s server VM count from resolved channel JSON; no default; required"
}

variable "vultr_server_plan" {
  type        = string
  description = "Vultr k3s server VM plan from resolved channel JSON; no default; required"
}

variable "vultr_agent_count" {
  type        = number
  description = "Vultr k3s agent VM count from resolved channel JSON; no default; required"
}

variable "vultr_agent_plan" {
  type        = string
  default     = "vc2-2c-4gb"
  description = "Vultr k3s agent VM plan. Default: vc2-2c-4gb."
}

variable "vultr_ssh_key_ids" {
  type        = list(string)
  description = "Operator-supplied Vultr SSH key IDs; no default; required"
}

variable "vultr_allowed_ssh_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach SSH on remote VMs; no default; required"
}

variable "vultr_remote_kubeconfig_path" {
  type        = string
  default     = "/root/humility-k3s.yaml"
  description = "Path where cloud-init copies the server kubeconfig. Default: /root/humility-k3s.yaml."
}

variable "vultr_firewall_name" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional explicit firewall group name. Default: null."
}

output "cluster_target" {
  value = module.platform_channel.cluster_target
}

output "server_ipv4" {
  value = module.platform_channel.server_ipv4
}

output "remote_kubeconfig_path" {
  value = module.platform_channel.remote_kubeconfig_path
}
