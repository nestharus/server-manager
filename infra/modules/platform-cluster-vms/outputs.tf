output "server_ids" {
  value = vultr_instance.server[*].id
}

output "server_ipv4" {
  value = vultr_instance.server[*].main_ip
}

output "agent_ids" {
  value = vultr_instance.agent[*].id
}

output "k3s_token" {
  value     = random_password.k3s_token.result
  sensitive = true
}

output "kubeconfig_path" {
  value = "/var/lib/rancher/k3s/server/cred/admin.kubeconfig (operator scp's from server)"
}
