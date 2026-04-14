variable "hcloud_token" {
  description = "Hetzner Cloud API token."
  type        = string
  sensitive   = true
}

variable "ssh_key_ids" {
  description = "Hetzner Cloud SSH key IDs available for node access."
  type        = list(number)
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "cluster_name" {
  description = "Cluster identifier."
  type        = string
}

variable "location" {
  description = "Hetzner location for cluster nodes."
  type        = string
  default     = "fsn1"
}

variable "control_plane_count" {
  description = "Number of control plane nodes (odd number for HA)"
  type        = number
  default     = 3

  validation {
    condition     = var.control_plane_count > 0 && var.control_plane_count % 2 == 1
    error_message = "Control plane count must be a positive odd number."
  }
}

variable "worker_count" {
  description = "Number of worker nodes"
  type        = number
  default     = 3

  validation {
    condition     = var.worker_count > 0
    error_message = "Worker count must be at least 1."
  }
}

variable "control_plane_server_type" {
  description = "Hetzner server type for control plane nodes."
  type        = string
  default     = "cpx22" # 2 vCPU, 4 GB RAM — EUR7.99/mo (cpx21 discontinued Jan 2026)
}

variable "worker_server_type" {
  description = "Hetzner server type for worker nodes."
  type        = string
  default     = "cpx32" # 2 vCPU, 8 GB RAM — EUR13.99/mo (cpx31 discontinued Jan 2026)
}

variable "k3s_version" {
  description = "Pinned k3s version for kube-hetzner."
  type        = string
  default     = "v1.35.3+k3s1" # Current stable as of April 2026
}

variable "network_zone" {
  description = "Hetzner private network zone."
  type        = string
  default     = "eu-central"
}

variable "ssh_public_key" {
  description = "SSH public key material required by the pinned kube-hetzner module."
  type        = string
}

variable "ssh_private_key" {
  description = "SSH private key material required by the pinned kube-hetzner module."
  type        = string
  sensitive   = true
}
