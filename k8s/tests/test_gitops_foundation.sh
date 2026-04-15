#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

require_dir() {
  local path="$1"
  local label="$2"

  [[ -d "$path" ]] || fail "$label is missing: $path"
}

has_manifest_files() {
  local dir="$1"

  find "$dir" -type f \( -iname '*.yaml' -o -iname '*.yml' -o -name 'Kustomization' \) -print -quit | grep -q .
}

require_manifest_files() {
  local dir="$1"
  local label="$2"

  has_manifest_files "$dir" || fail "$label must contain manifest files: $dir"
}

manifest_has_literal() {
  local needle="$1"
  local dir="$2"

  grep -R -I -F -n \
    --include='*.yaml' \
    --include='*.yml' \
    --include='Kustomization' \
    -- "$needle" "$dir" >/dev/null 2>&1
}

has_flux_toolkit_manifests() {
  local dir="$1"

  grep -R -I -F -n \
    --include='*.yaml' \
    --include='*.yml' \
    --include='Kustomization' \
    -- 'toolkit.fluxcd.io' "$dir" >/dev/null 2>&1
}

extract_flux_kustomization_paths() {
  local dir="$1"
  local file=""

  while IFS= read -r -d '' file; do
    awk '
      /^---[[:space:]]*$/ {
        saw_flux_api = 0
        in_flux_kustomization = 0
        next
      }

      /^[[:space:]]*apiVersion:[[:space:]]*/ {
        saw_flux_api = ($0 ~ /kustomize\.toolkit\.fluxcd\.io\//)
        next
      }

      /^[[:space:]]*kind:[[:space:]]*/ {
        in_flux_kustomization = (saw_flux_api && $0 ~ /kind:[[:space:]]*Kustomization([[:space:]]|$)/)
        next
      }

      in_flux_kustomization && /^[[:space:]]*path:[[:space:]]*/ {
        path = $0
        sub(/^[[:space:]]*path:[[:space:]]*/, "", path)
        gsub(/^[\"\047]/, "", path)
        gsub(/[\"\047]$/, "", path)
        gsub(/[[:space:]]+$/, "", path)
        print FILENAME ":" path
      }
    ' "$file"
  done < <(find "$dir" -type f \( -iname '*.yaml' -o -iname '*.yml' -o -name 'Kustomization' \) -print0)
}

normalize_flux_path() {
  local path="$1"

  path="${path#"${path%%[![:space:]]*}"}"
  path="${path%"${path##*[![:space:]]}"}"
  path="${path#./}"
  path="${path#/}"

  while [[ "$path" == *"/./"* ]]; do
    path="${path//\/.\//\/}"
  done

  while [[ "$path" == */ ]]; do
    path="${path%/}"
  done

  printf '%s' "$path"
}

validate_flux_path() {
  local raw_path="$1"
  local env_name="$2"
  local cluster_name="$3"
  local file="$4"
  local normalized=""

  normalized="$(normalize_flux_path "$raw_path")"

  [[ -n "$normalized" ]] || fail "empty Flux Kustomization path in $file"
  [[ "$normalized" != "." ]] || fail "Flux Kustomization in $file targets the repository root"
  [[ "$normalized" != "k8s" ]] || fail "Flux Kustomization in $file targets the k8s subtree root"
  [[ "$normalized" != "clusters" ]] || fail "Flux Kustomization in $file targets clusters/ instead of one cluster root"
  [[ "$normalized" != "k8s/clusters" ]] || fail "Flux Kustomization in $file targets k8s/clusters instead of one cluster root"
  [[ "$normalized" != "clusters/$env_name" ]] || fail "Flux Kustomization in $file targets clusters/$env_name instead of one cluster root"
  [[ "$normalized" != "k8s/clusters/$env_name" ]] || fail "Flux Kustomization in $file targets k8s/clusters/$env_name instead of one cluster root"
  [[ "$normalized" != ../* ]] || fail "Flux Kustomization path escapes upward from the repo root in $file: $raw_path"
  [[ "$normalized" != *"/../"* ]] || fail "Flux Kustomization path escapes a cluster root in $file: $raw_path"

  case "$normalized" in
    *clusters/"$env_name"/"$cluster_name"|*clusters/"$env_name"/"$cluster_name"/*)
      ;;
    *)
      fail "Flux Kustomization path in $file must stay inside clusters/$env_name/$cluster_name, found: $raw_path"
      ;;
  esac
}

check_base_layer() {
  local base_dir="$1"
  local banned=""

  require_dir "$base_dir" "base/"
  require_manifest_files "$base_dir" "base/"

  for banned in dev staging production control-cluster app-cluster; do
    if find "$base_dir" -type d -name "$banned" -print -quit | grep -q .; then
      fail "base/ must stay environment-neutral; found nested $banned directory under $base_dir"
    fi
  done

  if manifest_has_literal 'overlays/' "$base_dir"; then
    fail "base/ must not reference overlays/"
  fi

  if manifest_has_literal 'clusters/' "$base_dir"; then
    fail "base/ must not reference clusters/"
  fi
}

check_overlay_layer() {
  local overlays_dir="$1"
  local env_name="$2"
  local cluster_name="$3"
  local overlay_dir="$overlays_dir/$env_name/$cluster_name"

  require_dir "$overlay_dir" "overlay $env_name/$cluster_name"
  require_manifest_files "$overlay_dir" "overlay $env_name/$cluster_name"

  manifest_has_literal 'base/' "$overlay_dir" || fail "$overlay_dir must compose base/ content"

  if manifest_has_literal 'clusters/' "$overlay_dir"; then
    fail "$overlay_dir must not reference cluster roots directly"
  fi
}

check_cluster_root() {
  local clusters_dir="$1"
  local env_name="$2"
  local cluster_name="$3"
  local cluster_dir="$clusters_dir/$env_name/$cluster_name"
  local overlay_ref="overlays/$env_name/$cluster_name"
  local entry=""
  local file=""
  local raw_path=""
  local found_path=0

  require_dir "$cluster_dir" "cluster root $env_name/$cluster_name"
  require_manifest_files "$cluster_dir" "cluster root $env_name/$cluster_name"

  manifest_has_literal "$overlay_ref" "$cluster_dir" || fail "$cluster_dir must select $overlay_ref"
  has_flux_toolkit_manifests "$cluster_dir" || fail "$cluster_dir must contain Flux root objects"

  while IFS= read -r entry; do
    [[ -n "$entry" ]] || continue
    file="${entry%%:*}"
    raw_path="${entry#*:}"
    validate_flux_path "$raw_path" "$env_name" "$cluster_name" "$file"
    found_path=1
  done < <(extract_flux_kustomization_paths "$cluster_dir")

  [[ "$found_path" -eq 1 ]] || fail "$cluster_dir must contain at least one Flux Kustomization with spec.path"
}

check_buildkite_boundary() {
  local repo_root="$1"
  local file=""
  local mutation_pattern='kubectl([[:space:]]+[^#[:cntrl:]]*)?[[:space:]]+(apply|create|replace|patch|delete|annotate|label|scale|rollout[[:space:]]+restart|set[[:space:]]+image)|helm[[:space:]]+(install|upgrade|rollback|uninstall)|flux[[:space:]]+(reconcile|bootstrap|suspend|resume)'

  while IFS= read -r -d '' file; do
    if grep -I -n -E -- "$mutation_pattern" "$file" >/dev/null 2>&1; then
      fail "Buildkite must not mutate clusters directly; found a forbidden command in $file"
    fi
  done < <(
    find "$repo_root" -type f \
      \( -path '*/.buildkite/*' \
      -o -iname '*buildkite*.yml' \
      -o -iname '*buildkite*.yaml' \
      -o -iname '*buildkite*.json' \
      -o -iname '*buildkite*.sh' \) \
      -print0
  )
}

main() {
  local script_dir=""
  local repo_root=""
  local k8s_root=""
  local base_dir=""
  local overlays_dir=""
  local clusters_dir=""
  local env_name=""
  local cluster_name=""
  local environments=(dev staging production)
  local clusters=(control-cluster app-cluster)

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "$script_dir/../.." && pwd)"
  k8s_root="$repo_root/k8s"
  base_dir="$k8s_root/base"
  overlays_dir="$k8s_root/overlays"
  clusters_dir="$k8s_root/clusters"

  require_dir "$k8s_root" "k8s/"
  check_base_layer "$base_dir"
  require_dir "$overlays_dir" "overlays/"
  require_dir "$clusters_dir" "clusters/"

  for env_name in "${environments[@]}"; do
    require_dir "$overlays_dir/$env_name" "environment overlay directory $env_name"
    require_dir "$clusters_dir/$env_name" "environment cluster directory $env_name"

    for cluster_name in "${clusters[@]}"; do
      check_overlay_layer "$overlays_dir" "$env_name" "$cluster_name"
      check_cluster_root "$clusters_dir" "$env_name" "$cluster_name"
    done
  done

  check_buildkite_boundary "$repo_root"

  printf 'PASS: GitOps foundation topology checks succeeded.\n'
}

main "$@"
