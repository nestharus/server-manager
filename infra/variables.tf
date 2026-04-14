variable "vultr_api_key" {
  description = "Vultr API key"
  type        = string
  sensitive   = true
}

variable "ssh_key_id" {
  description = "Vultr SSH key ID (pre-registered)"
  type        = string
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "cluster_name" {
  description = "Cluster identifier."
  type        = string
}

variable "region" {
  description = "Vultr region for the cluster."
  type        = string
  default     = "ewr"
}

variable "worker_plan" {
  description = "Vultr plan for worker nodes."
  type        = string
}

variable "min_nodes" {
  description = "Minimum worker node count."
  type        = number
}

variable "max_nodes" {
  description = "Maximum worker node count for autoscaling."
  type        = number
}
