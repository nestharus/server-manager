variable "channel_id" {
  type        = string
  description = "Channel identifier used for names, tags, and labels; no default; required"
}

variable "cluster_name" {
  type        = string
  description = "Cluster name passed as the VM label and tag; no default; required"
}

variable "region" {
  type        = string
  description = "Vultr region code, for example ewr; no default; required"
}

variable "vpc_id" {
  type        = string
  description = "Existing Vultr VPC identifier from the platform-network module; no default; required"
}

variable "k3s_version" {
  type        = string
  description = "Pinned k3s version exported to the cloud-init installer; no default; required"
}

variable "server_count" {
  type        = number
  description = "Number of remote server VMs for the channel; no default; required"

  validation {
    condition     = var.server_count >= 1
    error_message = "server_count must be at least 1."
  }
}

variable "server_plan" {
  type        = string
  description = "Vultr instance plan for server VMs; no default; required"
}

variable "agent_count" {
  type        = number
  description = "Number of remote agent VMs for the channel; no default; required"

  validation {
    condition     = var.agent_count >= 0
    error_message = "agent_count must be at least 0."
  }
}

variable "agent_plan" {
  type        = string
  description = "Vultr instance plan for agent VMs; no default; required"
}

variable "os_id" {
  type        = number
  default     = 1743
  description = "Vultr OS ID for Ubuntu 22.04 LTS x64. Default: 1743."
}

variable "ssh_key_ids" {
  type        = list(string)
  description = "Operator-supplied Vultr SSH key IDs for apply-capable remote channels; no default; required"
}
