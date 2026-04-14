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
  description = "Number of control plane nodes."
  type        = number
}

variable "worker_count" {
  description = "Number of worker nodes."
  type        = number
}

variable "control_plane_server_type" {
  description = "Hetzner server type for control plane nodes."
  type        = string
  default     = "cpx21"
}

variable "worker_server_type" {
  description = "Hetzner server type for worker nodes."
  type        = string
  default     = "cpx21"
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
