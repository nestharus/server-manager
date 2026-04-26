variable "channel_id" {
  type        = string
  description = "Platform channel identifier; no default; required"
}

variable "cluster_target" {
  type        = string
  description = "Cluster target, either k3d-local or vultr-vms; no default; required"

  validation {
    condition     = contains(["k3d-local", "vultr-vms"], var.cluster_target)
    error_message = "cluster_target must be either k3d-local or vultr-vms."
  }
}

variable "cluster_distribution" {
  type        = string
  description = "Cluster distribution; no default; required"

  validation {
    condition     = var.cluster_distribution == "k3s"
    error_message = "cluster_distribution must be k3s."
  }
}

variable "cluster_k3s_version" {
  type        = string
  description = "Pinned k3s version for the selected channel target; no default; required"
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

variable "k3d_registry_port" {
  type        = number
  default     = 5000
  description = "Local k3d registry host port. Default: 5000."
}

variable "k3d_kubeconfig_path" {
  type        = string
  default     = "~/.kube/humility-local.yaml"
  description = "Path where the local channel kubeconfig is written. Default: ~/.kube/humility-local.yaml."
}

variable "vpc_v4_subnet" {
  type        = string
  default     = "10.40.0.0"
  description = "Base IPv4 subnet address for the channel VPC. Default: 10.40.0.0."
}

variable "vpc_v4_subnet_mask" {
  type        = number
  default     = 20
  description = "IPv4 subnet mask for the channel VPC. Default: 20."
}

variable "vultr_region" {
  type        = string
  default     = "ewr"
  description = "Vultr region for remote VM channels. Default: ewr."
}

variable "vultr_server_count" {
  type        = number
  default     = 1
  description = "Number of Vultr k3s server VMs. Default: 1."
}

variable "vultr_server_plan" {
  type        = string
  default     = "vc2-2c-4gb"
  description = "Vultr plan for k3s server VMs. Default: vc2-2c-4gb."
}

variable "vultr_agent_count" {
  type        = number
  default     = 0
  description = "Number of Vultr k3s agent VMs. Default: 0."
}

variable "vultr_agent_plan" {
  type        = string
  default     = "vc2-2c-4gb"
  description = "Vultr plan for k3s agent VMs. Default: vc2-2c-4gb."
}

variable "vultr_ssh_key_ids" {
  type        = list(string)
  default     = []
  description = "Operator-supplied Vultr SSH key IDs for apply-capable remote channels. Default: empty list."
}

variable "vultr_allowed_ssh_cidrs" {
  type        = list(string)
  default     = []
  description = "CIDRs allowed to reach SSH on remote VMs. Default: empty list."
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
