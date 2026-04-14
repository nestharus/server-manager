# Staging environment — on-demand, ephemeral
# Purpose: benchmarks, load tests, performance regression
# Spin up for release candidate validation, destroy after.
# Uses production-equivalent sizing for realistic benchmarks.
environment  = "staging"
cluster_name = "humility"
region       = "ewr"          # New Jersey
worker_plan  = "vc2-2c-4gb"   # 2 vCPU, 4 GB — $20/mo
min_nodes    = 3
max_nodes    = 6
