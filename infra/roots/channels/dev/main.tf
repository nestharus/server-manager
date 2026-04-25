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

  channel_id                 = var.channel_id
  channel_exposure           = var.channel_exposure
  tenant                     = var.tenant
  region                     = var.region
  vpc_v4_subnet              = var.vpc_v4_subnet
  vpc_v4_subnet_mask         = var.vpc_v4_subnet_mask
  cluster_label              = var.cluster_label
  cluster_kubernetes_version = var.cluster_kubernetes_version
  node_plan                  = var.node_plan
  node_quantity              = var.node_quantity
  ha_controlplanes           = var.ha_controlplanes
  enable_firewall            = var.enable_firewall
}

variable "channel_id" {
  description = "Channel identifier from resolved channel JSON; no default; required"
  type        = string
}

variable "channel_exposure" {
  description = "Channel exposure class from resolved channel JSON; no default; required"
  type        = string

  validation {
    condition     = contains(["prod", "stage", "dev"], var.channel_exposure)
    error_message = "channel_exposure must be one of: prod, stage, dev"
  }
}

variable "tenant" {
  description = "Optional tenant identifier from resolved channel JSON"
  type        = string
  default     = null
  nullable    = true
}

variable "region" {
  description = "Vultr region from resolved channel JSON; no default; required"
  type        = string
}

variable "vpc_v4_subnet" {
  description = "VPC IPv4 subnet from resolved channel JSON; no default; required"
  type        = string
}

variable "vpc_v4_subnet_mask" {
  description = "VPC IPv4 subnet mask from resolved channel JSON; no default; required"
  type        = number
}

variable "cluster_label" {
  description = "VKE cluster label from resolved channel JSON; no default; required"
  type        = string
}

variable "cluster_kubernetes_version" {
  description = "VKE Kubernetes version from resolved channel JSON; no default; required"
  type        = string
}

variable "node_plan" {
  description = "Default node pool plan from resolved channel JSON; no default; required"
  type        = string
}

variable "node_quantity" {
  description = "Default node pool size from resolved channel JSON; no default; required"
  type        = number
}

variable "ha_controlplanes" {
  description = "HA control plane flag from resolved channel JSON; no default; required"
  type        = bool
}

variable "enable_firewall" {
  description = "Managed firewall flag from resolved channel JSON; no default; required"
  type        = bool
}

output "vpc_id" {
  value = module.platform_channel.vpc_id
}

output "cluster_id" {
  value = module.platform_channel.cluster_id
}

output "endpoint" {
  value = module.platform_channel.endpoint
}
