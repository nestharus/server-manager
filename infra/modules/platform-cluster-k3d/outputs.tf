output "cluster_name" {
  description = "Name of the k3d cluster."
  value       = var.cluster_name
}

output "kubeconfig_path" {
  description = "Path to the generated kubeconfig file."
  value       = local.kubeconfig_path
}

output "registry_name" {
  description = "Name of the local Docker registry used by the cluster."
  value       = var.registry_name
}

output "registry_port" {
  description = "Host port exposed by the local Docker registry."
  value       = var.registry_port
}
