output "cluster_target" {
  value = var.cluster_target
}

output "server_ipv4" {
  value = var.cluster_target == "vultr-vms" ? module.cluster_vms[0].server_ipv4 : []
}

output "remote_kubeconfig_path" {
  value = var.cluster_target == "vultr-vms" ? module.cluster_vms[0].remote_kubeconfig_path : null
}
