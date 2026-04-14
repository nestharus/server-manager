environment               = "production"
cluster_name              = "humility"
location                  = "fsn1"
control_plane_count       = 3
worker_count              = 3          # 3 workers for workload distribution
control_plane_server_type = "cpx22"    # 2 vCPU, 4 GB — EUR7.99/mo
worker_server_type        = "cpx32"    # 4 vCPU, 8 GB — EUR13.99/mo
