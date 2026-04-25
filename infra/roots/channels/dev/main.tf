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
  type = string
}

variable "region" {
  type = string
}

variable "vpc_v4_subnet" {
  type = string
}

variable "vpc_v4_subnet_mask" {
  type = number
}

variable "cluster_label" {
  type = string
}

variable "cluster_kubernetes_version" {
  type = string
}

variable "node_plan" {
  type = string
}

variable "node_quantity" {
  type = number
}

variable "ha_controlplanes" {
  type = bool
}

variable "enable_firewall" {
  type = bool
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
