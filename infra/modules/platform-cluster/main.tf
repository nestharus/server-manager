# Platform cluster module — one VKE cluster per environment.

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "region" {
  description = "Vultr region"
  type        = string
}

variable "cluster_label" {
  description = "Cluster label"
  type        = string
}

variable "kubernetes_version" {
  description = "VKE Kubernetes version"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the platform cluster"
  type        = string
}

variable "node_plan" {
  description = "Plan for the default node pool"
  type        = string
}

variable "node_quantity" {
  description = "Node count for the default node pool"
  type        = number
}

variable "ha_controlplanes" {
  description = "Whether the cluster uses HA control planes"
  type        = bool
  default     = true
}

variable "enable_firewall" {
  description = "Whether to enable the managed Vultr firewall"
  type        = bool
  default     = true
}

resource "vultr_kubernetes" "platform" {
  region           = var.region
  label            = var.cluster_label
  version          = var.kubernetes_version
  vpc_id           = var.vpc_id
  ha_controlplanes = var.ha_controlplanes
  enable_firewall  = var.enable_firewall

  node_pools {
    label         = "${var.environment}-platform"
    plan          = var.node_plan
    node_quantity = var.node_quantity
    auto_scaler   = false
  }
}

output "cluster_id" {
  value = vultr_kubernetes.platform.id
}

output "endpoint" {
  value = vultr_kubernetes.platform.endpoint
}

output "kube_config" {
  value     = vultr_kubernetes.platform.kube_config
  sensitive = true
}

output "firewall_group_id" {
  value = vultr_kubernetes.platform.firewall_group_id
}
