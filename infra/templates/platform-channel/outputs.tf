output "cluster_target" {
  value = var.cluster_target
}

output "kubeconfig_path" {
  value = var.cluster_target == "k3d-local" ? module.cluster_k3d[0].kubeconfig_path : null
}

output "server_ipv4" {
  value = var.cluster_target == "vultr-vms" ? module.cluster_vms[0].server_ipv4 : []
}
