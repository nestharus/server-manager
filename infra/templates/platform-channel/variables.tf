variable "channel_id" {
  description = "Platform channel id; no default; required"
  type        = string
}

variable "channel_exposure" {
  type        = string
  description = "Channel exposure class: prod | stage | dev; sourced from resolved channel JSON; no default; required"

  validation {
    condition     = contains(["prod", "stage", "dev"], var.channel_exposure)
    error_message = "channel_exposure must be one of: prod, stage, dev"
  }
}

variable "tenant" {
  type        = string
  description = "Optional tenant identifier; null for non-tenant-scoped channels."
  default     = null
  nullable    = true
}

variable "region" {
  description = "Vultr region matching ^[a-z]{3}$; no default; required"
  type        = string
}

variable "vpc_v4_subnet" {
  description = "Base IPv4 subnet address for the channel VPC; no default; required"
  type        = string
}

variable "vpc_v4_subnet_mask" {
  description = "IPv4 subnet mask for the channel VPC; no default; required"
  type        = number
}

variable "cluster_label" {
  description = "VKE cluster label; no default; required"
  type        = string
}

variable "cluster_kubernetes_version" {
  description = "VKE Kubernetes version; no default; required"
  type        = string
}

variable "node_plan" {
  description = "Default node pool plan; no default; required"
  type        = string
}

variable "node_quantity" {
  description = "Default node pool node count; no default; required"
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
