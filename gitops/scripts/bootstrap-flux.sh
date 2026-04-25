#!/usr/bin/env bash
set -euo pipefail

# bootstrap-flux.sh - set up local age key, kind, local Git, and Flux.
#
# Local Git mechanism: the bootstrap seeds a bare copy of this worktree into an
# in-cluster git daemon served at git://git-local.git-system.svc.cluster.local.
# Flux reconciles from that service, so the proof path does not use GitHub,
# Vultr, real DNS, or any hosted Git service.

readonly AGE_KEY_DIR="${AGE_KEY_DIR:-${HOME}/.config/sops/age}"
readonly DEV_AGE_KEY="${AGE_KEY_DIR}/dev.txt"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
readonly GITOPS_DIR="${REPO_ROOT}/gitops"
readonly KIND_CLUSTER_NAME="${KIND_CLUSTER:-server-manager-dev}"
readonly LOCAL_GIT_NAMESPACE="git-system"
readonly LOCAL_GIT_DEPLOYMENT="git-local"
readonly LOCAL_GIT_SERVICE="git-local"
readonly LOCAL_GIT_BRANCH="${LOCAL_GIT_BRANCH:-main}"
readonly LOCAL_GIT_ROOT="${REPO_ROOT}/.tmp/local-git"
readonly LOCAL_BARE_REPO="${LOCAL_GIT_ROOT}/server-manager.git"
readonly LOCAL_GIT_URL="git://git-local.git-system.svc.cluster.local/server-manager.git"

ensure_age_installed() {
  command -v age-keygen >/dev/null || {
    echo "ERROR: age-keygen not installed. Run gitops/scripts/install-tools.sh first."
    return 1
  }
}

ensure_dev_age_key() {
  mkdir -p "$AGE_KEY_DIR"
  if [[ -f "$DEV_AGE_KEY" ]]; then
    echo "dev age key already exists at $DEV_AGE_KEY"
  else
    age-keygen -o "$DEV_AGE_KEY"
    echo "generated dev age key at $DEV_AGE_KEY"
    echo "Public recipient (add to gitops/secrets/dev/.sops.yaml):"
    age-keygen -y "$DEV_AGE_KEY"
  fi
}

ensure_kind_installed() {
  command -v kind >/dev/null || {
    echo "ERROR: kind not installed. Run gitops/scripts/install-tools.sh first."
    return 1
  }
}

ensure_flux_installed() {
  command -v flux >/dev/null || {
    echo "ERROR: flux CLI not installed. Run gitops/scripts/install-tools.sh first."
    return 1
  }
}

ensure_kubectl_installed() {
  command -v kubectl >/dev/null || {
    echo "ERROR: kubectl not installed. Run gitops/scripts/install-tools.sh first."
    return 1
  }
}

create_kind_cluster() {
  local cluster_name="$KIND_CLUSTER_NAME"

  if kind get clusters | grep -qx "$cluster_name"; then
    echo "kind cluster '${cluster_name}' already exists"
  else
    kind create cluster --name "$cluster_name" --wait 60s
    echo "created kind cluster '${cluster_name}'"
  fi

  kubectl config use-context "kind-${cluster_name}"
}

flux_check_pre() {
  flux check --pre || {
    echo "ERROR: flux pre-check failed; cluster is not Flux-ready"
    return 1
  }
}

seed_local_git_repo() {
  local head

  mkdir -p "$LOCAL_GIT_ROOT"
  rm -rf "$LOCAL_BARE_REPO"

  head="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  git clone --bare "$REPO_ROOT" "$LOCAL_BARE_REPO" >/dev/null
  git --git-dir="$LOCAL_BARE_REPO" update-ref "refs/heads/${LOCAL_GIT_BRANCH}" "$head"
  git --git-dir="$LOCAL_BARE_REPO" config daemon.uploadpack true
  git --git-dir="$LOCAL_BARE_REPO" config http.receivepack false
  touch "${LOCAL_BARE_REPO}/git-daemon-export-ok"

  echo "seeded local Git source at ${LOCAL_BARE_REPO} (${LOCAL_GIT_BRANCH} -> ${head})"
}

start_local_git_server() {
  local pod

  seed_local_git_repo

  kubectl create namespace "$LOCAL_GIT_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${LOCAL_GIT_DEPLOYMENT}
  namespace: ${LOCAL_GIT_NAMESPACE}
  labels:
    app.kubernetes.io/name: ${LOCAL_GIT_DEPLOYMENT}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: ${LOCAL_GIT_DEPLOYMENT}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${LOCAL_GIT_DEPLOYMENT}
    spec:
      containers:
        - name: git-daemon
          image: alpine/git:2.49.1
          imagePullPolicy: IfNotPresent
          command:
            - /bin/sh
            - -c
            - |
              mkdir -p /git
              exec git daemon --verbose --export-all --reuseaddr --base-path=/git --listen=0.0.0.0 /git
          ports:
            - name: git
              containerPort: 9418
          volumeMounts:
            - name: git-data
              mountPath: /git
      volumes:
        - name: git-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ${LOCAL_GIT_SERVICE}
  namespace: ${LOCAL_GIT_NAMESPACE}
spec:
  selector:
    app.kubernetes.io/name: ${LOCAL_GIT_DEPLOYMENT}
  ports:
    - name: git
      port: 9418
      targetPort: git
YAML

  kubectl -n "$LOCAL_GIT_NAMESPACE" rollout status "deployment/${LOCAL_GIT_DEPLOYMENT}" --timeout=2m
  pod="$(kubectl -n "$LOCAL_GIT_NAMESPACE" get pod \
    -l "app.kubernetes.io/name=${LOCAL_GIT_DEPLOYMENT}" \
    -o jsonpath='{.items[0].metadata.name}')"

  kubectl -n "$LOCAL_GIT_NAMESPACE" exec "$pod" -- rm -rf /git/server-manager.git
  tar -C "$LOCAL_GIT_ROOT" -cf - server-manager.git \
    | kubectl -n "$LOCAL_GIT_NAMESPACE" exec -i "$pod" -- tar -C /git -xf -
  kubectl -n "$LOCAL_GIT_NAMESPACE" exec "$pod" -- \
    git --git-dir=/git/server-manager.git rev-parse "refs/heads/${LOCAL_GIT_BRANCH}" >/dev/null

  echo "local Git source ready at ${LOCAL_GIT_URL}"
}

wait_for_flux_controllers() {
  kubectl -n flux-system wait deployment --all --for=condition=Available --timeout=5m
}

bootstrap_flux() {
  flux_check_pre
  start_local_git_server

  kubectl apply -f "${GITOPS_DIR}/bases/flux-system/gotk-components.yaml"
  wait_for_flux_controllers

  kubectl apply -k "${GITOPS_DIR}/channels/dev"
  flux reconcile source git server-manager --namespace flux-system --timeout 2m
  flux reconcile kustomization server-manager-dev --namespace flux-system --timeout 5m
}

verify_reconciled() {
  flux get sources git --namespace flux-system
  flux get kustomizations --namespace flux-system
  kubectl wait --for=condition=Ready gitrepository/server-manager -n flux-system --timeout=2m
  kubectl wait --for=condition=Ready kustomization/server-manager-dev -n flux-system --timeout=5m
}

teardown_kind_cluster() {
  kind delete cluster --name "$KIND_CLUSTER_NAME"
}

usage() {
  cat <<'EOF'
Usage: bootstrap-flux.sh <command>

Commands:
  age-key      Generate the dev channel's local age private key (idempotent)
  cluster-up   Create the kind cluster and run flux pre-check
  bootstrap    Full local bootstrap: kind + local Git + Flux reconcile dev channel
  teardown     Delete the kind cluster
  help         Show this help
EOF
}

main() {
  local mode="${1:-help}"

  case "$mode" in
    age-key)
      ensure_age_installed
      ensure_dev_age_key
      ;;
    cluster-up)
      ensure_kind_installed
      ensure_flux_installed
      ensure_kubectl_installed
      create_kind_cluster
      flux_check_pre
      ;;
    bootstrap)
      ensure_age_installed
      ensure_kind_installed
      ensure_flux_installed
      ensure_kubectl_installed
      ensure_dev_age_key
      create_kind_cluster
      bootstrap_flux
      verify_reconciled
      ;;
    teardown)
      ensure_kind_installed
      teardown_kind_cluster
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "ERROR: unknown command: ${mode}" >&2
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
