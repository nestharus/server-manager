# Platform network module — one VPC per channel.
#
# Each channel gets a non-overlapping subnet from the 10.40.0.0/16 range:
#   dev:        10.40.0.0/20
#   staging:    10.40.16.0/20
#   production: 10.40.32.0/20

variable "channel" {
  description = "Channel name"
  type        = string
}

variable "region" {
  description = "Vultr region"
  type        = string
}

variable "v4_subnet" {
  description = "Base subnet for the channel VPC"
  type        = string
}

variable "v4_subnet_mask" {
  description = "Subnet mask for the channel VPC"
  type        = number
  default     = 20
}

resource "vultr_vpc" "platform" {
  description    = "humility-${var.channel}-platform"
  region         = var.region
  v4_subnet      = var.v4_subnet
  v4_subnet_mask = var.v4_subnet_mask
}

output "vpc_id" {
  value = vultr_vpc.platform.id
}

output "description" {
  value = vultr_vpc.platform.description
}

output "v4_subnet" {
  value = vultr_vpc.platform.v4_subnet
}

output "v4_subnet_mask" {
  value = vultr_vpc.platform.v4_subnet_mask
}
