variable "channel_id" {
  type        = string
  description = "Channel identifier used to label the local platform cluster; no default; required"
}

variable "cluster_name" {
  type        = string
  description = "k3d cluster name resolved for the local platform channel; no default; required"
}

variable "k3s_version" {
  type        = string
  description = "Pinned k3s version used for the local k3d node image; no default; required"
}

variable "servers" {
  type        = number
  default     = 1
  description = "Number of k3d server nodes."
}

variable "agents" {
  type        = number
  default     = 1
  description = "Number of k3d agent nodes."
}

variable "registry_name" {
  type        = string
  default     = "humility-local"
  description = "Name of the local k3d registry."
}

variable "registry_port" {
  type        = number
  default     = 5000
  description = "Host port exposed by the local k3d registry."
}

variable "kubeconfig_path" {
  type        = string
  default     = "~/.kube/humility-local.yaml"
  description = "Path where the channel-scoped kubeconfig will be written."
}
