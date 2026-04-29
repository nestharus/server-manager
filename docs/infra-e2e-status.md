# INIT-119 Infra E2E Status

Generated: 2026-04-29T08:05:04Z

Bring-up seconds: NOT RECORDED

| Flow | Status | Evidence |
|---|---:|---|
| 01-cluster-up | PASS | live nodes include bootstrap fixture roles (2 nodes) (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/01-cluster-up.log) |
| 02-flux-reconciles | PASS | GitRepository/humility-local Ready=True (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/02-flux-reconciles.log) |
| 03-sops-bootstrap | PASS | SOPS boundary fixtures distinguish encrypted and plaintext secret data (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/03-sops-bootstrap.log) |
| 04-infisical-runtime | PASS | Infisical plaintext fixture value is absent from GitOps secret paths (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/04-infisical-runtime.log) |
| 05-storage | PASS | validate-object-storage completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/05-storage.log) |
| 06-tls-dns | PASS | validate-tls-dns completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/06-tls-dns.log) |
| 07-app-cluster | PASS | validate-app-clusters completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/07-app-cluster.log) |
| 08-cluster-security | PASS | validate-cluster-security completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/08-cluster-security.log) |
| 09-image-registry | PASS | validate-container-delivery completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/09-image-registry.log) |
| 10-buildkite | PASS | validate-buildkite completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/10-buildkite.log) |
| 11-ingress | PASS | validate-kong-ingress completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/11-ingress.log) |
| 12-data-plane | PASS | validate-data-plane completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/12-data-plane.log) |
| 13-backup-dr | PASS | validate-backup-dr completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/13-backup-dr.log) |
| 14-application-workloads | PASS | validate-application-workloads completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/14-application-workloads.log) |
| 15-auth-stack | PASS | validate-auth-stack completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/15-auth-stack.log) |
| 16-access-policy | PASS | validate-access-policy completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/16-access-policy.log) |
| 17-tenant-isolation | PASS | validate-tenant-isolation completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/17-tenant-isolation.log) |
| 18-observability | PASS | validate-observability completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/18-observability.log) |
| 19-web-ui | PASS | validate-web-ui completed (log: /home/nes/projects/server-manager/worktrees/recovery-test-first-audit/.tmp/init-119-e2e/logs/19-web-ui.log) |
