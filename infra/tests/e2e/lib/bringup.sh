#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi

source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"

E2E_EXTERNAL_IMAGES=(
  "ghcr.io/fluxcd/source-controller:v1.8.3"
  "ghcr.io/fluxcd/kustomize-controller:v1.8.4"
  "alpine/git:v2.45.2"
  "arigaio/atlas-operator:0.7.28"
  "ghcr.io/cloudnative-pg/cloudnative-pg:1.29.0"
  "xpkg.crossplane.io/crossplane/crossplane:v1.20.7"
  "infisical/infisical:v0.151.0"
  "infisical/kubernetes-operator:v0.10.32"
  "mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16"
  "mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18"
  "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
  "quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727"
  "quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z"
  "quay.io/jetstack/cert-manager-controller:v1.20.2"
  "quay.io/jetstack/cert-manager-webhook:v1.20.2"
  "quay.io/jetstack/cert-manager-cainjector:v1.20.2"
  "quay.io/jetstack/cert-manager-startupapicheck:v1.20.2"
  "cr.smallstep.com/smallstep/step-ca:0.30.2"
  "cr.smallstep.com/smallstep/step-ca-bootstrap:latest@sha256:5270356cf91596afe18478eab60c6c0866b2cc62618f282d42827e58f84d6eae"
  "cr.step.sm/smallstep/step-issuer:0.10.2"
  "busybox:1.37.0"
  "kong:3.9"
  "kong/kubernetes-ingress-controller:3.5"
  "ghcr.io/goauthentik/server:2026.2.2"
  "pomerium/pomerium:v0.22.1"
  "docker.io/permitio/opal-client-cedar:0.7.12"
  "docker.io/permitio/opal-server:0.7.12"
  "curlimages/curl:8.16.0"
  "apteno/alpine-jq:2021-04-25"
  "buildkite/agent:3.104.0"
  "docker:29.0.4-cli"
  "grafana/grafana:11.2.0"
  "grafana/loki:3.1.1"
  "prom/prometheus:v2.54.1"
  "prom/alertmanager:v0.27.0"
  "otel/opentelemetry-collector-contrib:0.106.1"
  "bitnami/kubectl@sha256:98736aabcecb8d3cbcdcd7b132d14b1d67ed99bac2f06d471f06235933103df3"
)

e2e_bootstrap_optional_secrets() {
  require_cluster

  if [[ -z "${BUILDKITE_AGENT_TOKEN:-}" ]]; then
    echo "SKIP: Buildkite agent token bootstrap requires BUILDKITE_AGENT_TOKEN"
  fi
}

e2e_build_local_images() {
  if [[ "${E2E_SKIP_IMAGE_BUILD:-0}" == "1" ]]; then
    echo "SKIP: image builds skipped by E2E_SKIP_IMAGE_BUILD=1"
    return 0
  fi

  "${REPO_ROOT}/infra/scripts/build-channel-image.sh" \
    --channel local \
    --app registry-smoke \
    --tag init-109-local \
    --context "${REPO_ROOT}/containers/samples/registry-smoke" \
    --file "${REPO_ROOT}/containers/samples/registry-smoke/Containerfile"

  "${REPO_ROOT}/infra/scripts/build-server-manager-images.sh" \
    --channel local \
    --tag init-113-local

  "${REPO_ROOT}/infra/scripts/build-channel-image.sh" \
    --channel local \
    --app server-manager-web \
    --tag init-118-local \
    --context "$REPO_ROOT" \
    --file "${REPO_ROOT}/containers/server-manager/Containerfile.web"
}

e2e_k3d_import_image() {
  local image="$1"
  local import_ref="$image"
  local archive
  local archive_name
  local node
  local nodes=()

  if [[ "$image" == *@sha256:* ]]; then
    local name_without_digest="${image%@*}"
    local name_leaf="${name_without_digest##*/}"
    local digest="${image##*@sha256:}"

    if [[ "$name_leaf" == *:* ]]; then
      import_ref="$name_without_digest"
    else
      import_ref="${name_without_digest}:sha-${digest:0:12}"
    fi

    if ! docker image inspect "$import_ref" >/dev/null 2>&1; then
      local image_id
      image_id="$(docker image inspect --format '{{.Id}}' "$image")"
      docker tag "$image_id" "$import_ref"
    fi
  fi

  echo "IMAGE: importing ${import_ref} into humility-local"
  mapfile -t nodes < <(
    docker ps \
      --filter "name=^k3d-humility-local-(server|agent)-[0-9]+$" \
      --format '{{.Names}}' \
      | sort
  )

  if [[ "${#nodes[@]}" -eq 0 ]]; then
    echo "WARN: no k3d runtime nodes found; falling back to k3d image import" >&2
    k3d image import --cluster humility-local "$import_ref"
    return
  fi

  archive="$(mktemp "${TMPDIR:-/tmp}/humility-e2e-image.XXXXXX.tar")"
  archive_name="$(basename "$archive")"
  if ! docker save "$import_ref" -o "$archive"; then
    rm -f "$archive"
    return 1
  fi
  if ! python3 - "$archive" <<'PY'
import json
import sys
import tarfile

archive = sys.argv[1]
with tarfile.open(archive) as tar:
    names = set(tar.getnames())
    manifest = json.load(tar.extractfile("manifest.json"))

missing = []
for entry in manifest:
    for name in [entry.get("Config"), *entry.get("Layers", [])]:
        if name and name not in names:
            missing.append(name)

if missing:
    print(f"archive missing blobs: {', '.join(missing[:5])}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    echo "WARN: Docker archive for ${import_ref} is incomplete; runtime pull will use the configured registry endpoints" >&2
    rm -f "$archive"
    return 1
  fi
  for node in "${nodes[@]}"; do
    echo "IMAGE: loading ${import_ref} into ${node}"
    if ! docker cp "$archive" "${node}:/tmp/${archive_name}"; then
      rm -f "$archive"
      return 1
    fi
    if ! docker exec "$node" ctr -n k8s.io images import "/tmp/${archive_name}" >/dev/null; then
      docker exec "$node" rm -f "/tmp/${archive_name}" >/dev/null || true
      rm -f "$archive"
      return 1
    fi
    docker exec "$node" rm -f "/tmp/${archive_name}" >/dev/null
  done
  rm -f "$archive"
}

e2e_pull_external_images() {
  if [[ "${E2E_SKIP_EXTERNAL_IMAGE_PULL:-0}" == "1" ]]; then
    echo "SKIP: external image pre-pull skipped by E2E_SKIP_EXTERNAL_IMAGE_PULL=1"
    return 0
  fi

  local image
  local attempt
  for image in "${E2E_EXTERNAL_IMAGES[@]}"; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      echo "IMAGE: already present ${image}"
    else
      echo "IMAGE: pulling ${image}"
      for attempt in 1 2 3; do
        if docker pull "$image"; then
          break
        fi
        if [[ "$attempt" -eq 3 ]]; then
          echo "FAIL: could not pull ${image}" >&2
          return 1
        fi
        sleep $((attempt * 10))
      done
    fi

    if ! e2e_k3d_import_image "$image"; then
      echo "WARN: could not pre-import ${image}; runtime pull will use the configured registry endpoints" >&2
    fi
  done
}

e2e_wait_bringup_ready() {
  require_cluster
  kubectl_cmd -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=300s
  kubectl_cmd -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=900s
  kubectl_cmd -n kube-system rollout status deployment/coredns --timeout=180s
}

e2e_bringup_fullstack() {
  local started_at
  local finished_at
  started_at="$(date +%s)"
  mkdir -p "$E2E_ARTIFACT_DIR" "$E2E_DIAGNOSTICS_DIR"

  "${REPO_ROOT}/infra/scripts/install-cluster-tools.sh" --install --no-color
  "${REPO_ROOT}/infra/scripts/install-cluster-tools.sh" --check --no-color

  "${REPO_ROOT}/infra/scripts/bring-up-local-channel.sh" --channel local --force --cluster-only
  e2e_pull_external_images
  e2e_build_local_images

  if ! "${REPO_ROOT}/infra/scripts/bring-up-local-channel.sh" --channel local; then
    capture_k8s_diagnostics "bring-up-local-channel"
    echo "WARN: local channel installer did not complete; continuing to the E2E readiness gate"
  fi

  e2e_bootstrap_optional_secrets
  e2e_wait_bringup_ready || {
    capture_k8s_diagnostics "ready-wait"
    return 1
  }

  finished_at="$(date +%s)"
  printf '%s\n' "$((finished_at - started_at))" >"${E2E_ARTIFACT_DIR}/bringup-seconds.txt"
  echo "BRINGUP_SECONDS=$((finished_at - started_at))"
}
