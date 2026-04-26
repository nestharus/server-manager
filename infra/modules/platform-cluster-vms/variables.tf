variable "channel_id" {
  type        = string
  description = "Channel identifier used for names, tags, and labels; no default; required"
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
  default     = 1
  description = "Number of remote server VMs for INIT-101. Default: 1."

  validation {
    condition     = var.server_count >= 1
    error_message = "server_count must be at least 1."
  }
}

variable "server_plan" {
  type        = string
  default     = "vc2-2c-4gb"
  description = "Vultr instance plan for server VMs. Default: vc2-2c-4gb."
}

variable "agent_count" {
  type        = number
  default     = 0
  description = "Number of remote agent VMs for INIT-101. Default: 0."

  validation {
    condition     = var.agent_count >= 0
    error_message = "agent_count must be at least 0."
  }
}

variable "agent_plan" {
  type        = string
  default     = "vc2-2c-4gb"
  description = "Vultr instance plan for future agent VMs. Default: vc2-2c-4gb."
}

variable "ssh_key_ids" {
  type        = list(string)
  description = "Operator-supplied Vultr SSH key IDs for apply-capable remote channels; no default; required"

  validation {
    condition     = length(var.ssh_key_ids) > 0
    error_message = "ssh_key_ids must contain at least one SSH key ID."
  }
}

variable "allowed_ssh_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach SSH on remote VMs; no default; required"

  validation {
    condition = alltrue([
      for cidr in var.allowed_ssh_cidrs : can(cidrhost(cidr, 0)) && length(split("/", cidr)) == 2
    ])
    error_message = "allowed_ssh_cidrs must contain valid CIDR strings."
  }
}

variable "remote_kubeconfig_path" {
  type        = string
  default     = "/root/humility-k3s.yaml"
  description = "Path where cloud-init copies the server kubeconfig. Default: /root/humility-k3s.yaml."
}

variable "firewall_name" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional explicit firewall group name. Default: null."
}
