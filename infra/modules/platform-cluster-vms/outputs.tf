output "server_ids" {
  value = concat(vultr_instance.server[*].id, vultr_instance.server_joiner[*].id)
}

output "server_ipv4" {
  value = concat(vultr_instance.server[*].main_ip, vultr_instance.server_joiner[*].main_ip)
}

output "server_internal_ip" {
  value = concat(vultr_instance.server[*].internal_ip, vultr_instance.server_joiner[*].internal_ip)
}

output "agent_ids" {
  value = vultr_instance.agent[*].id
}

output "k3s_token" {
  value     = random_password.k3s_token.result
  sensitive = true
}

output "remote_kubeconfig_path" {
  value = var.remote_kubeconfig_path
}
