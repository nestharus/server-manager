#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RUN_CLUSTER=0
CLUSTER_EXERCISED=0

pass() {
  echo "  PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

skip() {
  echo "  SKIP: $1"
  SKIP_COUNT=$((SKIP_COUNT + 1))
}

usage() {
  cat <<'EOF'
Usage: validate_platform_bootstrap.sh [--cluster]

Validates platform bootstrap files and local channel tooling.

Options:
  --cluster   Run the full local k3d bring-up, kubectl, idempotency, and delete proof
  -h, --help  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)
      RUN_CLUSTER=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

assert_file_exists() {
  local file="$1"
  if [[ -f "${INFRA_DIR}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "missing: ${file}"
  fi
}

assert_dir_exists() {
  local path="$1"
  if [[ -d "${INFRA_DIR}/${path}" ]]; then
    pass "directory exists: ${path}"
  else
    fail "missing directory: ${path}"
  fi
}

assert_executable() {
  local file="$1"
  if [[ -x "${INFRA_DIR}/${file}" ]]; then
    pass "executable: ${file}"
  else
    fail "not executable: ${file}"
  fi
}

assert_path_absent() {
  local path="$1"
  if [[ ! -e "${INFRA_DIR}/${path}" ]]; then
    pass "absent: ${path}"
  else
    fail "still exists: ${path}"
  fi
}

assert_repo_path_absent() {
  local path="$1"
  if [[ ! -e "${REPO_ROOT}/${path}" ]]; then
    pass "absent: ${path}"
  else
    fail "still exists: ${path}"
  fi
}

assert_repo_file_exists() {
  local file="$1"
  if [[ -f "${REPO_ROOT}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "missing: ${file}"
  fi
}

assert_file_contains() {
  local file="$1"
  local pattern="$2"
  local description="$3"

  if grep -q -- "$pattern" "${INFRA_DIR}/${file}"; then
    pass "$description"
  else
    fail "$description"
  fi
}

assert_sops_bootstrap_boundary() {
  local sops_config="${REPO_ROOT}/.sops.yaml"
  local sentinel="${REPO_ROOT}/gitops/bootstrap/sops-sentinel.enc.yaml"
  local infisical_bootstrap="${REPO_ROOT}/gitops/bootstrap/infisical-server-bootstrap.enc.yaml"
  local linter="${INFRA_DIR}/scripts/lint-sops-boundary.py"
  local py_bin

  assert_repo_file_exists ".sops.yaml"

  if ! py_bin="$(python_bin)"; then
    fail ".sops.yaml creation rule"
  elif "$py_bin" - "$sops_config" <<'PY'
import sys
from pathlib import Path

import yaml

data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
rules = data.get("creation_rules") if isinstance(data, dict) else None
if not isinstance(rules, list) or len(rules) != 1:
    raise SystemExit("expected exactly one creation_rule")
rule = rules[0]
if rule.get("path_regex") != r"^gitops/bootstrap/.*\.enc\.yaml$":
    raise SystemExit("creation_rule path_regex mismatch")
if rule.get("encrypted_regex") != "^(data|stringData)$":
    raise SystemExit("creation_rule encrypted_regex mismatch")
age = rule.get("age")
if not isinstance(age, str) or not age.startswith("age1"):
    raise SystemExit("creation_rule age recipient missing")
PY
  then
    pass ".sops.yaml creation rule"
  else
    fail ".sops.yaml creation rule"
  fi

  assert_repo_file_exists "gitops/bootstrap/sops-sentinel.enc.yaml"
  if [[ -f "$sentinel" ]] && grep -q '^sops:' "$sentinel" && grep -q '^[[:space:]]*mac:' "$sentinel"; then
    pass "sops sentinel is encrypted"
  else
    fail "sops sentinel is encrypted"
  fi

  assert_repo_file_exists "gitops/bootstrap/infisical-server-bootstrap.enc.yaml"
  if [[ -f "$infisical_bootstrap" ]] \
    && grep -q '^sops:' "$infisical_bootstrap" \
    && grep -q '^[[:space:]]*mac:' "$infisical_bootstrap" \
    && grep -q 'name: infisical-server-bootstrap' "$infisical_bootstrap" \
    && grep -q 'namespace: infisical-system' "$infisical_bootstrap"; then
    pass "Infisical server bootstrap Secret is encrypted"
  else
    fail "Infisical server bootstrap Secret is encrypted"
  fi

  if [[ -n "${py_bin:-}" && -f "$linter" ]] && "$py_bin" "$linter" >/dev/null; then
    pass "SOPS boundary lint accepts bootstrap allowlist"
  else
    fail "SOPS boundary lint accepts bootstrap allowlist"
  fi

  assert_file_exists "scripts/bootstrap-sops-age-key.sh"
  assert_executable "scripts/bootstrap-sops-age-key.sh"
}

assert_infisical_identity_bootstrap_script() {
  local script="${INFRA_DIR}/scripts/bootstrap-infisical-identity.sh"
  local operator_crd="${REPO_ROOT}/gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml"
  local help_output

  assert_file_exists "scripts/bootstrap-infisical-identity.sh"
  assert_executable "scripts/bootstrap-infisical-identity.sh"

  if help_output="$(bash "$script" --help 2>&1)" \
    && grep -q 'Usage: bootstrap-infisical-identity.sh' <<<"$help_output" \
    && grep -q 'Re-running is idempotent' <<<"$help_output"; then
    pass "bootstrap-infisical-identity --help"
  else
    fail "bootstrap-infisical-identity --help"
  fi

  if grep -q '^UA_SECRET_NAME="infisical-operator-auth"$' "$script" \
    && grep -q '^UA_SECRET_NAMESPACE="infisical-system"$' "$script" \
    && grep -q -- '--from-literal=clientId=' "$script" \
    && grep -q -- '--from-literal=clientSecret=' "$script"; then
    pass "Operator UA Secret is kubectl-applied with clientId/clientSecret"
  else
    fail "Operator UA Secret is kubectl-applied with clientId/clientSecret"
  fi

  if grep -q 'universalAuth:' "$operator_crd" \
    && grep -q 'credentialsRef:' "$operator_crd" \
    && grep -q 'secretName:' "$operator_crd" \
    && grep -q 'secretNamespace:' "$operator_crd"; then
    pass "Infisical Operator CRD reads Universal Auth credentialsRef Secret"
  else
    fail "Infisical Operator CRD reads Universal Auth credentialsRef Secret"
  fi
}

assert_gitops_channel_schema_rendering() {
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/gitops"
  local local_resolved="${tmp_dir}/local.resolved.json"
  local dev_resolved="${tmp_dir}/dev.resolved.json"
  local out_dir="${REPO_ROOT}/.tmp/gitops-source/local"
  local before
  local after
  local render_status
  local rerender_status
  local py_bin

  if ! py_bin="$(python_bin)"; then
    fail "python interpreter available for GitOps rendering"
    return
  fi

  rm -rf "$tmp_dir" "${REPO_ROOT}/.tmp/gitops-source"
  mkdir -p "$tmp_dir"

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel local --out "$local_resolved" \
    && "$py_bin" - "$local_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "source_kind": "git",
    "git_url": "http://git-local.git-system.svc.cluster.local:8080/cgi-bin/git/humility-local.git",
    "git_ref": "refs/heads/main",
    "path": "./gitops/channels/local",
    "kustomization_name": "humility-local",
    "kustomization_namespace": "flux-system",
    "sops_age_secret_name": "sops-age",
    "decryption_secret_namespace": "flux-system",
    "interval": "1m",
    "retry_interval": "1m",
    "prune": True,
    "wait": True,
}
if data.get("gitops") != expected:
    raise SystemExit(f"unexpected gitops block: {data.get('gitops')!r}")
PY
  then
    pass "local channel resolves with operator-supplied gitops block"
  else
    fail "local channel resolves with operator-supplied gitops block"
  fi

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$dev_resolved" \
    && "$py_bin" - "$dev_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if "gitops" in data:
    raise SystemExit("dev must omit gitops in INIT-102")
PY
  then
    pass "dev channel validates without gitops block"
  else
    fail "dev channel validates without gitops block"
  fi

  set +e
  "$py_bin" "${INFRA_DIR}/scripts/render-gitops-source.py" --channel local --out "$out_dir" >/dev/null
  render_status=$?
  set -e

  if [[ "$render_status" -eq 0 ]]; then
    pass "render-gitops-source local exits 0"
  else
    fail "render-gitops-source local exits 0"
    return
  fi

  for file in \
    "gitops/sources/local/gitrepository.yaml" \
    "gitops/sources/local/kustomization.yaml" \
    "gitops/sources/local/kustomization.kustomize.yaml" \
    "gitops/channels/local/generated/gitops-snapshot-marker.yaml" \
    "gitops/bootstrap/infisical-server-bootstrap.enc.yaml"; do
    if [[ -f "${out_dir}/${file}" ]]; then
      pass "rendered: ${file}"
    else
      fail "missing rendered file: ${file}"
    fi
  done

  before="$(find "$out_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"
  set +e
  "$py_bin" "${INFRA_DIR}/scripts/render-gitops-source.py" --channel local --out "$out_dir" >/dev/null
  rerender_status=$?
  set -e
  after="$(find "$out_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"

  if [[ "$rerender_status" -eq 0 && "$before" == "$after" ]]; then
    pass "render-gitops-source is byte-identical on rerun"
  else
    fail "render-gitops-source is byte-identical on rerun"
  fi
}

assert_infisical_channel_schema_and_sample() {
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/infisical-channel"
  local local_resolved="${tmp_dir}/local.resolved.json"
  local dev_resolved="${tmp_dir}/dev.resolved.json"
  local registry="${tmp_dir}/channels"
  local sample_dir="${REPO_ROOT}/gitops/channels/local/infisical/sample"
  local sample_cr="${sample_dir}/infisicalsecret.yaml"
  local operator_crd="${REPO_ROOT}/gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml"
  local py_bin

  if ! py_bin="$(python_bin)"; then
    fail "python interpreter available for Infisical channel validation"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel local --out "$local_resolved" \
    && "$py_bin" - "$local_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "server_url": "http://infisical.infisical-system.svc.cluster.local:8080",
    "project_id": "platform-local",
    "environment": "local",
    "secrets_path": "/sample",
    "auth_method": "universal-auth",
    "universal_auth_secret_name": "infisical-operator-auth",
    "universal_auth_secret_namespace": "infisical-system",
    "operator_namespace": "infisical-system",
    "resync_interval": "60s",
}
if data.get("infisical") != expected:
    raise SystemExit(f"unexpected infisical block: {data.get('infisical')!r}")
PY
  then
    pass "local channel resolves with operator-supplied infisical block"
  else
    fail "local channel resolves with operator-supplied infisical block"
  fi

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$dev_resolved" \
    && "$py_bin" - "$dev_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if "infisical" in data:
    raise SystemExit("dev must omit infisical in INIT-103")
PY
  then
    pass "dev channel validates without infisical block"
  else
    fail "dev channel validates without infisical block"
  fi

  if "$py_bin" - "${INFRA_DIR}/scripts" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import resolve_platform_channel as resolver

resolved = resolver.resolve_channel("local-child")
if resolved.get("infisical", {}).get("project_id") != "platform-local":
    raise SystemExit(f"local-child did not inherit infisical: {resolved.get('infisical')!r}")
PY
  then
    pass "local child channel inherits infisical block"
  else
    fail "local child channel inherits infisical block"
  fi

  cp -R "${INFRA_DIR}/channels" "$registry"
  if "$py_bin" - "${registry}/local.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
data.pop("infisical", None)
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
  then
    if "$py_bin" "${INFRA_DIR}/scripts/validate_platform_channels.py" --registry "$registry" >/dev/null 2>&1; then
      fail "local k3d channel without infisical fails schema validation"
    else
      pass "local k3d channel without infisical fails schema validation"
    fi
  else
    fail "local k3d channel without infisical fails schema validation"
  fi

  rm -rf "$registry"
  cp -R "${INFRA_DIR}/channels" "$registry"
  if "$py_bin" - "${registry}/local.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
data["infisical"]["server_url"] = "http://infisical.infisical-system.svc.cluster.local:8080/"
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
  then
    if "$py_bin" "${INFRA_DIR}/scripts/validate_platform_channels.py" --registry "$registry" >/dev/null 2>&1; then
      fail "infisical server_url rejects trailing slash"
    else
      pass "infisical server_url rejects trailing slash"
    fi
  else
    fail "infisical server_url rejects trailing slash"
  fi

  assert_repo_file_exists "gitops/channels/local/infisical/sample/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/sample/namespace.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/sample/infisicalsecret.yaml"

  if command -v kubectl >/dev/null 2>&1 && kubectl kustomize "$sample_dir" >/dev/null; then
    pass "kubectl kustomize Infisical sample"
  else
    fail "kubectl kustomize Infisical sample"
  fi

  if "$py_bin" - "$sample_cr" "$operator_crd" <<'PY'
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

sample = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
crd_path = Path(sys.argv[2])
schema = None

for document in yaml.safe_load_all(crd_path.read_text(encoding="utf-8")):
    if not isinstance(document, dict):
        continue
    if document.get("kind") != "CustomResourceDefinition":
        continue
    if document.get("metadata", {}).get("name") != "infisicalsecrets.secrets.infisical.com":
        continue
    for version in document.get("spec", {}).get("versions", []):
        if version.get("name") == "v1alpha1":
            schema = version.get("schema", {}).get("openAPIV3Schema")
            break

if not isinstance(schema, dict):
    raise SystemExit("InfisicalSecret v1alpha1 CRD schema not found")

errors = sorted(Draft7Validator(schema).iter_errors(sample), key=lambda item: list(item.path))
if errors:
    raise SystemExit(errors[0].message)

if sample.get("apiVersion") != "secrets.infisical.com/v1alpha1":
    raise SystemExit("apiVersion mismatch")
if sample.get("kind") != "InfisicalSecret":
    raise SystemExit("kind mismatch")
if sample.get("metadata", {}).get("name") != "infisical-local-sample":
    raise SystemExit("metadata.name mismatch")
if sample.get("metadata", {}).get("namespace") != "infisical-sample":
    raise SystemExit("metadata.namespace mismatch")

spec = sample.get("spec", {})
auth = spec.get("authentication", {}).get("universalAuth", {})
scope = auth.get("secretsScope", {})
creds = auth.get("credentialsRef", {})
target = spec.get("managedSecretReference", {})

expected = {
    ("spec", "hostAPI"): "http://infisical.infisical-system.svc.cluster.local:8080",
    ("scope", "projectSlug"): "platform-local",
    ("scope", "envSlug"): "local",
    ("scope", "secretsPath"): "/sample",
    ("creds", "secretName"): "infisical-operator-auth",
    ("creds", "secretNamespace"): "infisical-system",
    ("target", "secretName"): "infisical-local-sample",
    ("target", "secretNamespace"): "infisical-sample",
}
actual_maps = {"spec": spec, "scope": scope, "creds": creds, "target": target}
for (section, key), value in expected.items():
    if actual_maps[section].get(key) != value:
        raise SystemExit(f"{section}.{key} mismatch: {actual_maps[section].get(key)!r}")
PY
  then
    pass "sample InfisicalSecret conforms to pinned CRD schema"
  else
    fail "sample InfisicalSecret conforms to pinned CRD schema"
  fi
}

assert_object_storage_channel_schema() {
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/object-storage-channel"
  local local_resolved="${tmp_dir}/local.resolved.json"
  local dev_resolved="${tmp_dir}/dev.resolved.json"
  local registry="${tmp_dir}/channels"
  local py_bin

  if ! py_bin="$(python_bin)"; then
    fail "python interpreter available for object-storage channel validation"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel local --out "$local_resolved" \
    && "$py_bin" - "$local_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "provider": "minio",
    "endpoint": "http://minio.minio-system.svc.cluster.local:9000",
    "region": "us-east-1",
    "bucket": "humility-local-sample",
    "credentials_secret_name": "minio-root",
    "credentials_secret_namespace": "minio-system",
    "infisical_project": "platform-storage",
    "infisical_path": "/object-storage/local/",
}
if data.get("object_storage") != expected:
    raise SystemExit(f"unexpected object_storage block: {data.get('object_storage')!r}")
PY
  then
    pass "local channel resolves with required MinIO object_storage block"
  else
    fail "local channel resolves with required MinIO object_storage block"
  fi

  if "$py_bin" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel dev --out "$dev_resolved" \
    && "$py_bin" - "$dev_resolved" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
storage = data.get("object_storage")
if storage is None:
    raise SystemExit("dev object_storage block is absent")
if storage.get("provider") != "vultr-object-storage":
    raise SystemExit(f"unexpected dev provider: {storage!r}")
if storage.get("endpoint") != "https://ewr1.vultrobjects.com":
    raise SystemExit(f"unexpected dev endpoint: {storage!r}")
if "gitops" in data or "infisical" in data:
    raise SystemExit("dev must keep remote GitOps and Infisical omitted")
PY
  then
    pass "dev channel validates with optional Vultr object_storage block"
  else
    fail "dev channel validates with optional Vultr object_storage block"
  fi

  if "$py_bin" - "${INFRA_DIR}/scripts" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import resolve_platform_channel as resolver

resolved = resolver.resolve_channel("local-child")
if resolved.get("object_storage", {}).get("provider") != "minio":
    raise SystemExit(f"local-child did not inherit object_storage: {resolved.get('object_storage')!r}")
PY
  then
    pass "local child channel inherits object_storage block"
  else
    fail "local child channel inherits object_storage block"
  fi

  rm -rf "$registry"
  cp -R "${INFRA_DIR}/channels" "$registry"
  if "$py_bin" - "${registry}/local.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
data.pop("object_storage", None)
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
  then
    if "$py_bin" "${INFRA_DIR}/scripts/validate_platform_channels.py" --registry "$registry" >/dev/null 2>&1; then
      fail "local k3d channel without object_storage fails schema validation"
    else
      pass "local k3d channel without object_storage fails schema validation"
    fi
  else
    fail "local k3d channel without object_storage fails schema validation"
  fi

  rm -rf "$registry"
  cp -R "${INFRA_DIR}/channels" "$registry"
  if "$py_bin" - "${registry}/dev.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
data["object_storage"].pop("endpoint", None)
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
  then
    if "$py_bin" "${INFRA_DIR}/scripts/validate_platform_channels.py" --registry "$registry" \
      && "$py_bin" - "${INFRA_DIR}/scripts" "$registry" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import resolve_platform_channel as resolver

registry = Path(sys.argv[2])
resolver.CHANNELS_DIR = registry
resolver.FIXTURES_DIR = registry / "fixtures"
data = resolver.resolve_channel("dev")
if data.get("object_storage", {}).get("endpoint") != "https://ewr1.vultrobjects.com":
    raise SystemExit(data.get("object_storage"))
PY
    then
      pass "Vultr object_storage endpoint resolves from region"
    else
      fail "Vultr object_storage endpoint resolves from region"
    fi
  else
    fail "Vultr object_storage endpoint resolves from region"
  fi

  for alias in s3 endpoint_url secret_namespace; do
    rm -rf "$registry"
    cp -R "${INFRA_DIR}/channels" "$registry"
    if "$py_bin" - "${registry}/local.yaml" "$alias" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
alias = sys.argv[2]
data = yaml.safe_load(path.read_text(encoding="utf-8"))
data["object_storage"][alias] = "rejected"
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
    then
      if "$py_bin" "${INFRA_DIR}/scripts/validate_platform_channels.py" --registry "$registry" >/dev/null 2>&1; then
        fail "object_storage alias ${alias} is rejected"
      else
        pass "object_storage alias ${alias} is rejected"
      fi
    else
      fail "object_storage alias ${alias} is rejected"
    fi
  done
}

assert_object_storage_infisical_bootstrap() {
  local script="${INFRA_DIR}/scripts/bootstrap-infisical-storage.sh"
  local storage_dir="${REPO_ROOT}/gitops/channels/local/object-storage/infisical"
  local storage_cr="${storage_dir}/minio-root-infisicalsecret.yaml"
  local operator_crd="${REPO_ROOT}/gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml"
  local help_output
  local py_bin

  assert_file_exists "scripts/bootstrap-infisical-storage.sh"
  assert_executable "scripts/bootstrap-infisical-storage.sh"

  if help_output="$(bash "$script" --help 2>&1)" \
    && grep -q 'Usage: bootstrap-infisical-storage.sh' <<<"$help_output" \
    && grep -q 'Re-running is idempotent' <<<"$help_output" \
    && grep -q 'storage-specific Universal Auth Secret' <<<"$help_output"; then
    pass "bootstrap-infisical-storage --help"
  else
    fail "bootstrap-infisical-storage --help"
  fi

  if grep -q '^UA_SECRET_NAME="infisical-operator-auth"$' "$script" \
    && grep -q '^UA_SECRET_NAMESPACE="infisical-system"$' "$script" \
    && ! grep -q 'infisical-storage-operator-auth' "$script" \
    && ! grep -q -- '--from-literal=clientId=' "$script" \
    && ! grep -q -- '--from-literal=clientSecret=' "$script"; then
    pass "storage bootstrap reuses INIT-103 Operator UA Secret"
  else
    fail "storage bootstrap reuses INIT-103 Operator UA Secret"
  fi

  assert_repo_file_exists "gitops/channels/local/object-storage/infisical/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/infisical/minio-root-infisicalsecret.yaml"

  if command -v kubectl >/dev/null 2>&1 && kubectl kustomize "$storage_dir" >/dev/null; then
    pass "kubectl kustomize object-storage InfisicalSecret"
  else
    fail "kubectl kustomize object-storage InfisicalSecret"
  fi

  if ! py_bin="$(python_bin)"; then
    fail "object-storage InfisicalSecret conforms to pinned CRD schema"
  elif "$py_bin" - "$storage_cr" "$operator_crd" <<'PY'
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

storage = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
crd_path = Path(sys.argv[2])
schema = None

for document in yaml.safe_load_all(crd_path.read_text(encoding="utf-8")):
    if not isinstance(document, dict):
        continue
    if document.get("kind") != "CustomResourceDefinition":
        continue
    if document.get("metadata", {}).get("name") != "infisicalsecrets.secrets.infisical.com":
        continue
    for version in document.get("spec", {}).get("versions", []):
        if version.get("name") == "v1alpha1":
            schema = version.get("schema", {}).get("openAPIV3Schema")
            break

if not isinstance(schema, dict):
    raise SystemExit("InfisicalSecret v1alpha1 CRD schema not found")

errors = sorted(Draft7Validator(schema).iter_errors(storage), key=lambda item: list(item.path))
if errors:
    raise SystemExit(errors[0].message)

if storage.get("apiVersion") != "secrets.infisical.com/v1alpha1":
    raise SystemExit("apiVersion mismatch")
if storage.get("kind") != "InfisicalSecret":
    raise SystemExit("kind mismatch")
if storage.get("metadata", {}).get("name") != "minio-root":
    raise SystemExit("metadata.name mismatch")
if storage.get("metadata", {}).get("namespace") != "minio-system":
    raise SystemExit("metadata.namespace mismatch")

spec = storage.get("spec", {})
auth = spec.get("authentication", {}).get("universalAuth", {})
scope = auth.get("secretsScope", {})
creds = auth.get("credentialsRef", {})
target = spec.get("managedSecretReference", {})
template = target.get("template", {})

expected = {
    ("spec", "hostAPI"): "http://infisical.infisical-system.svc.cluster.local:8080",
    ("scope", "projectSlug"): "platform-storage",
    ("scope", "envSlug"): "local",
    ("scope", "secretsPath"): "/object-storage/local/",
    ("creds", "secretName"): "infisical-operator-auth",
    ("creds", "secretNamespace"): "infisical-system",
    ("target", "secretName"): "minio-root",
    ("target", "secretNamespace"): "minio-system",
    ("target", "creationPolicy"): "Owner",
}
actual_maps = {"spec": spec, "scope": scope, "creds": creds, "target": target}
for (section, key), value in expected.items():
    if actual_maps[section].get(key) != value:
        raise SystemExit(f"{section}.{key} mismatch: {actual_maps[section].get(key)!r}")

if scope.get("recursive") is not False:
    raise SystemExit("recursive must be false")
if template.get("includeAllSecrets") is not True:
    raise SystemExit("includeAllSecrets must be true")
PY
  then
    pass "object-storage InfisicalSecret conforms to pinned CRD schema"
  else
    fail "object-storage InfisicalSecret conforms to pinned CRD schema"
  fi
}

assert_object_storage_minio_manifests() {
  local storage_dir="${REPO_ROOT}/gitops/channels/local/object-storage"
  local minio_dir="${storage_dir}/minio"
  local rendered="${REPO_ROOT}/.tmp/validate-platform-bootstrap/object-storage-rendered.yaml"
  local py_bin

  assert_repo_file_exists "gitops/channels/local/object-storage/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/namespace.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/minio/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/minio/serviceaccount.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/minio/pvc.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/minio/deployment.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/minio/service.yaml"

  mkdir -p "$(dirname "$rendered")"
  if command -v kubectl >/dev/null 2>&1 && kubectl kustomize "$storage_dir" >"$rendered"; then
    pass "kubectl kustomize object-storage local subtree"
  else
    fail "kubectl kustomize object-storage local subtree"
    return
  fi

  if grep -R -Eq '^[[:space:]]*kind:[[:space:]]*(HelmRelease|OCIRepository|Tenant|AdminJob)[[:space:]]*$' "$storage_dir"; then
    fail "object-storage raw manifests exclude Helm, Tenant, and AdminJob resources"
  else
    pass "object-storage raw manifests exclude Helm, Tenant, and AdminJob resources"
  fi

  if grep -R -Eq '^[[:space:]]*kind:[[:space:]]*(ClusterRole|ClusterRoleBinding|Role|RoleBinding)[[:space:]]*$' "$minio_dir"; then
    fail "MinIO ServiceAccount has no RBAC binding"
  else
    pass "MinIO ServiceAccount has no RBAC binding"
  fi

  if ! py_bin="$(python_bin)"; then
    fail "MinIO rendered manifest contract"
  elif "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

docs = [doc for doc in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")) if isinstance(doc, dict)]
by_kind_name = {(doc.get("kind"), doc.get("metadata", {}).get("name")): doc for doc in docs}

namespace = by_kind_name.get(("Namespace", "minio-system"))
if namespace is None:
    raise SystemExit("Namespace/minio-system missing")

sa = by_kind_name.get(("ServiceAccount", "minio"))
if sa is None or sa.get("metadata", {}).get("namespace") != "minio-system":
    raise SystemExit("ServiceAccount/minio missing or wrong namespace")
if sa.get("automountServiceAccountToken") is not False:
    raise SystemExit("ServiceAccount/minio must disable token automount")

pvc = by_kind_name.get(("PersistentVolumeClaim", "minio-data"))
if pvc is None:
    raise SystemExit("PVC/minio-data missing")
if pvc.get("metadata", {}).get("namespace") != "minio-system":
    raise SystemExit("PVC/minio-data wrong namespace")
if pvc.get("spec", {}).get("storageClassName") != "local-path":
    raise SystemExit("PVC/minio-data must use local-path")
if pvc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage") != "10Gi":
    raise SystemExit("PVC/minio-data must request 10Gi")

svc = by_kind_name.get(("Service", "minio"))
if svc is None:
    raise SystemExit("Service/minio missing")
ports = svc.get("spec", {}).get("ports", [])
if len(ports) != 1 or ports[0].get("port") != 9000 or ports[0].get("targetPort") != "s3":
    raise SystemExit(f"Service/minio must expose only 9000: {ports!r}")
if svc.get("spec", {}).get("type") != "ClusterIP":
    raise SystemExit("Service/minio must be ClusterIP")

deployment = by_kind_name.get(("Deployment", "minio"))
if deployment is None:
    raise SystemExit("Deployment/minio missing")
spec = deployment.get("spec", {})
template = spec.get("template", {}).get("spec", {})
containers = template.get("containers", [])
if spec.get("replicas") != 1:
    raise SystemExit("Deployment/minio must run one replica")
if spec.get("strategy", {}).get("type") != "Recreate":
    raise SystemExit("Deployment/minio must use Recreate strategy")
if template.get("serviceAccountName") != "minio" or template.get("automountServiceAccountToken") is not False:
    raise SystemExit("Deployment/minio must use minio ServiceAccount without token automount")
if len(containers) != 1:
    raise SystemExit("Deployment/minio must have one container")
container = containers[0]
expected_image = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"
if container.get("image") != expected_image:
    raise SystemExit(f"unexpected image: {container.get('image')!r}")
env = {item.get("name"): item for item in container.get("env", [])}
if env.get("MINIO_BROWSER", {}).get("value") != "off":
    raise SystemExit("MINIO_BROWSER must be off")
for name in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
    ref = env.get(name, {}).get("valueFrom", {}).get("secretKeyRef", {})
    if ref != {"name": "minio-root", "key": name}:
        raise SystemExit(f"{name} must come from Secret/minio-root")
resources = container.get("resources", {})
if resources.get("requests") != {"cpu": "250m", "memory": "512Mi"}:
    raise SystemExit(f"request mismatch: {resources.get('requests')!r}")
if resources.get("limits") != {"cpu": "1", "memory": "1Gi"}:
    raise SystemExit(f"limit mismatch: {resources.get('limits')!r}")
for probe in ("livenessProbe", "readinessProbe"):
    http_get = container.get(probe, {}).get("httpGet", {})
    if http_get.get("port") != "s3" or not str(http_get.get("path", "")).startswith("/minio/health/"):
        raise SystemExit(f"{probe} must use MinIO health endpoint on s3 port")
PY
  then
    pass "MinIO rendered manifest contract"
  else
    fail "MinIO rendered manifest contract"
  fi

  if grep -q 'object-storage' "${REPO_ROOT}/gitops/channels/local/kustomization.yaml"; then
    pass "local channel kustomization includes object-storage subtree"
  else
    fail "local channel kustomization includes object-storage subtree"
  fi
}

assert_object_storage_bucket_job() {
  local storage_dir="${REPO_ROOT}/gitops/channels/local/object-storage"
  local buckets_dir="${storage_dir}/buckets"
  local rendered="${REPO_ROOT}/.tmp/validate-platform-bootstrap/object-storage-buckets-rendered.yaml"
  local py_bin

  assert_repo_file_exists "gitops/channels/local/object-storage/buckets/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/buckets/serviceaccount.yaml"
  assert_repo_file_exists "gitops/channels/local/object-storage/buckets/job.yaml"

  mkdir -p "$(dirname "$rendered")"
  if command -v kubectl >/dev/null 2>&1 && kubectl kustomize "$storage_dir" >"$rendered"; then
    pass "kubectl kustomize object-storage bucket Job"
  else
    fail "kubectl kustomize object-storage bucket Job"
    return
  fi

  if grep -R -Eq '^[[:space:]]*kind:[[:space:]]*(ClusterRole|ClusterRoleBinding|Role|RoleBinding|CronJob)[[:space:]]*$' "$buckets_dir"; then
    fail "bucket Job excludes RBAC bindings and CronJob"
  else
    pass "bucket Job excludes RBAC bindings and CronJob"
  fi

  if ! py_bin="$(python_bin)"; then
    fail "bucket Job rendered manifest contract"
  elif "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

docs = [doc for doc in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")) if isinstance(doc, dict)]
by_kind_name = {(doc.get("kind"), doc.get("metadata", {}).get("name")): doc for doc in docs}

sa = by_kind_name.get(("ServiceAccount", "create-sample-bucket"))
if sa is None:
    raise SystemExit("ServiceAccount/create-sample-bucket missing")
if sa.get("metadata", {}).get("namespace") != "minio-system":
    raise SystemExit("bucket ServiceAccount wrong namespace")
if sa.get("automountServiceAccountToken") is not False:
    raise SystemExit("bucket ServiceAccount must disable token automount")

job = by_kind_name.get(("Job", "create-sample-bucket"))
if job is None:
    raise SystemExit("Job/create-sample-bucket missing")
metadata = job.get("metadata", {})
if metadata.get("namespace") != "minio-system":
    raise SystemExit("bucket Job wrong namespace")
if "ttlSecondsAfterFinished" in job.get("spec", {}):
    raise SystemExit("bucket Job must not set ttlSecondsAfterFinished")
template = job.get("spec", {}).get("template", {}).get("spec", {})
if template.get("serviceAccountName") != "create-sample-bucket":
    raise SystemExit("bucket Job must use create-sample-bucket ServiceAccount")
if template.get("automountServiceAccountToken") is not False:
    raise SystemExit("bucket Job must disable token automount")
if template.get("restartPolicy") != "OnFailure":
    raise SystemExit("bucket Job restartPolicy must be OnFailure")
containers = template.get("containers", [])
if len(containers) != 1:
    raise SystemExit("bucket Job must have one container")
container = containers[0]
expected_image = "quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727"
if container.get("image") != expected_image:
    raise SystemExit(f"unexpected mc image: {container.get('image')!r}")
command = "\n".join(str(part) for part in container.get("command", []))
for expected in (
    "mc alias set",
    "mc ready",
    "mc mb --ignore-existing local/humility-local-sample",
):
    if expected not in command:
        raise SystemExit(f"missing command fragment: {expected}")
if "humility-local-sample" not in command or command.count("humility-local-sample") != 1:
    raise SystemExit("bucket Job must create exactly the sample bucket")
env = {item.get("name"): item for item in container.get("env", [])}
for name in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
    ref = env.get(name, {}).get("valueFrom", {}).get("secretKeyRef", {})
    if ref != {"name": "minio-root", "key": name}:
        raise SystemExit(f"{name} must come from Secret/minio-root")
PY
  then
    pass "bucket Job rendered manifest contract"
  else
    fail "bucket Job rendered manifest contract"
  fi

  if grep -q 'buckets' "${REPO_ROOT}/gitops/channels/local/object-storage/kustomization.yaml"; then
    pass "object-storage kustomization includes bucket Job"
  else
    fail "object-storage kustomization includes bucket Job"
  fi
}

assert_gitops_flux_components() {
  local file="${REPO_ROOT}/gitops/flux/gotk-components.yaml"
  local deployment_count
  local unexpected_deployment_count

  if [[ -f "$file" ]]; then
    pass "exists: gitops/flux/gotk-components.yaml"
  else
    fail "missing: gitops/flux/gotk-components.yaml"
    return
  fi

  deployment_count="$(grep -c '^kind: Deployment$' "$file" || true)"
  if [[ "$deployment_count" == "2" ]]; then
    pass "Flux lockfile has exactly 2 Deployments"
  else
    fail "Flux lockfile has exactly 2 Deployments"
  fi

  if awk 'BEGIN { RS = "---"; found = 0 } /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*source-controller/ { found = 1 } END { exit found ? 0 : 1 }' "$file"; then
    pass "Flux lockfile includes source-controller Deployment"
  else
    fail "Flux lockfile includes source-controller Deployment"
  fi

  if awk 'BEGIN { RS = "---"; found = 0 } /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*kustomize-controller/ { found = 1 } END { exit found ? 0 : 1 }' "$file"; then
    pass "Flux lockfile includes kustomize-controller Deployment"
  else
    fail "Flux lockfile includes kustomize-controller Deployment"
  fi

  unexpected_deployment_count="$(
    awk '
      BEGIN { RS = "---"; count = 0 }
      /kind:[[:space:]]*Deployment/ && /name:[[:space:]]*(helm-controller|notification-controller|image-reflector-controller|image-automation-controller)/ {
        count += 1
      }
      END { print count }
    ' "$file"
  )"
  if [[ "$unexpected_deployment_count" == "0" ]]; then
    pass "Flux lockfile excludes helm/notification/image controller Deployments"
  else
    fail "Flux lockfile excludes helm/notification/image controller Deployments"
  fi
}

assert_infisical_server_raw_manifests() {
  local server_dir="${REPO_ROOT}/gitops/channels/local/infisical/server"
  local rendered="${server_dir}/rendered/infisical-standalone-1.8.0.yaml"
  local before
  local after
  local render_output
  local render_status
  local py_bin

  assert_repo_file_exists "gitops/channels/local/infisical/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/server/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/server/namespace.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/server/service-alias.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/server/render-values.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/server/rendered/infisical-standalone-1.8.0.yaml"
  assert_file_exists "scripts/render-infisical-manifests.sh"
  assert_executable "scripts/render-infisical-manifests.sh"

  if grep -R -Eq '^[[:space:]]*kind:[[:space:]]*(HelmRelease|OCIRepository)[[:space:]]*$' "$server_dir"; then
    fail "Infisical server raw manifests exclude HelmRelease and OCIRepository"
  else
    pass "Infisical server raw manifests exclude HelmRelease and OCIRepository"
  fi

  if grep -R -Eq '(meta\.helm\.sh|helm\.sh/hook|updatedAt|app\.kubernetes\.io/managed-by:[[:space:]]*Helm|heritage:[[:space:]]*Helm)' "$server_dir"; then
    fail "Infisical server raw manifests exclude Helm ownership metadata"
  else
    pass "Infisical server raw manifests exclude Helm ownership metadata"
  fi

  if ! py_bin="$(python_bin)"; then
    fail "Infisical server image pins"
  elif "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

expected = {
    "infisical/infisical:v0.151.0",
    "mirror.gcr.io/bitnamilegacy/postgresql:16.2.0-debian-11-r16",
    "mirror.gcr.io/bitnamilegacy/redis:7.2.4-debian-11-r18",
}
found = set()


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "image" and isinstance(child, str):
                found.add(child)
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)


for document in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")):
    walk(document)

if found != expected:
    raise SystemExit(f"image set mismatch: found={sorted(found)!r}")
PY
  then
    pass "Infisical server image pins"
  else
    fail "Infisical server image pins"
  fi

  if [[ -n "${py_bin:-}" ]] && "$py_bin" - "${server_dir}/render-values.yaml" "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

values = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
rendered = list(yaml.safe_load_all(Path(sys.argv[2]).read_text(encoding="utf-8")))

postgres = values["postgresql"]
redis = values["redis"]
assert postgres["auth"]["existingSecret"] == "infisical-server-bootstrap"
assert postgres["auth"]["secretKeys"]["userPasswordKey"] == "POSTGRES_PASSWORD"
assert postgres["auth"]["secretKeys"]["adminPasswordKey"] == "POSTGRES_POSTGRES_PASSWORD"
assert postgres["useExistingPostgresSecret"]["existingConnectionStringSecret"]["name"] == "infisical-server-bootstrap"
assert postgres["useExistingPostgresSecret"]["existingConnectionStringSecret"]["key"] == "DB_CONNECTION_URI"
assert redis["auth"]["existingSecret"] == "infisical-server-bootstrap"
assert redis["auth"]["existingSecretPasswordKey"] == "REDIS_PASSWORD"

for document in rendered:
    if not isinstance(document, dict):
        continue
    metadata = document.get("metadata") or {}
    if document.get("kind") == "Secret" and metadata.get("name") in {"postgresql", "redis"}:
        raise SystemExit("rendered chart must not create credential Secret with literal data")
    if document.get("kind") != "Deployment" or metadata.get("name") != "infisical-infisical-standalone-infisical":
        continue
    env = document["spec"]["template"]["spec"]["containers"][0]["env"]
    refs = {
        item["name"]: item.get("valueFrom", {}).get("secretKeyRef")
        for item in env
        if item.get("name") in {"DB_CONNECTION_URI", "REDIS_URL"}
    }
    assert refs == {
        "DB_CONNECTION_URI": {"name": "infisical-server-bootstrap", "key": "DB_CONNECTION_URI"},
        "REDIS_URL": {"name": "infisical-server-bootstrap", "key": "REDIS_URL"},
    }
    break
else:
    raise SystemExit("Infisical server Deployment not found")
PY
  then
    pass "Infisical server credentials reference SOPS bootstrap Secret"
  else
    fail "Infisical server credentials reference SOPS bootstrap Secret"
  fi

  if [[ -n "${py_bin:-}" ]] && "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

namespaced = {
    "ConfigMap",
    "Deployment",
    "NetworkPolicy",
    "PersistentVolumeClaim",
    "Role",
    "RoleBinding",
    "Secret",
    "Service",
    "ServiceAccount",
    "StatefulSet",
}

missing = []
for document in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")):
    if not isinstance(document, dict) or document.get("kind") not in namespaced:
        continue
    metadata = document.get("metadata") or {}
    if metadata.get("namespace") != "infisical-system":
        missing.append(f"{document.get('kind')}/{metadata.get('name')}")

if missing:
    raise SystemExit(f"missing namespace: {missing}")
PY
  then
    pass "Infisical server namespaced resources set explicit namespace"
  else
    fail "Infisical server namespaced resources set explicit namespace"
  fi

  if grep -q '^namespace:' "${server_dir}/kustomization.yaml"; then
    fail "Infisical server kustomization avoids namespace transformer"
  else
    pass "Infisical server kustomization avoids namespace transformer"
  fi

  before="$(find "$server_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"
  set +e
  render_output="$(bash "${INFRA_DIR}/scripts/render-infisical-manifests.sh" --check 2>&1)"
  render_status=$?
  set -e
  after="$(find "$server_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"

  if [[ "$render_status" -eq 0 && "$before" == "$after" ]]; then
    pass "Infisical server render is byte-identical on rerun"
  else
    echo "$render_output"
    fail "Infisical server render is byte-identical on rerun"
  fi
}

assert_infisical_operator_raw_manifests() {
  local operator_dir="${REPO_ROOT}/gitops/channels/local/infisical/operator"
  local rendered="${operator_dir}/rendered/secrets-operator-0.10.32.yaml"
  local expected_crds=(
    "clustergenerators.secrets.infisical.com"
    "infisicaldynamicsecrets.secrets.infisical.com"
    "infisicalpushsecrets.secrets.infisical.com"
    "infisicalsecrets.secrets.infisical.com"
    "passwords.secrets.infisical.com"
    "uuids.secrets.infisical.com"
  )
  local before
  local after
  local render_output
  local render_status
  local py_bin

  assert_repo_file_exists "gitops/channels/local/infisical/operator/kustomization.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/operator/render-values.yaml"
  assert_repo_file_exists "gitops/channels/local/infisical/operator/rendered/secrets-operator-0.10.32.yaml"

  if grep -R -Eq '^[[:space:]]*kind:[[:space:]]*(HelmRelease|OCIRepository)[[:space:]]*$' "${REPO_ROOT}/gitops/channels/local/infisical"; then
    fail "Infisical raw manifests exclude HelmRelease and OCIRepository"
  else
    pass "Infisical raw manifests exclude HelmRelease and OCIRepository"
  fi

  if grep -R -Eq '(meta\.helm\.sh|helm\.sh/hook|updatedAt|app\.kubernetes\.io/managed-by:[[:space:]]*Helm|heritage:[[:space:]]*Helm)' "$operator_dir"; then
    fail "Infisical Operator raw manifests exclude Helm ownership metadata"
  else
    pass "Infisical Operator raw manifests exclude Helm ownership metadata"
  fi

  if ! py_bin="$(python_bin)"; then
    fail "Infisical Operator CRDs from secrets.infisical.com"
    fail "Infisical Operator image pin"
  elif "$py_bin" - "$rendered" "${expected_crds[@]}" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
expected = set(sys.argv[2:])
found = set()

for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
    if not isinstance(document, dict) or document.get("kind") != "CustomResourceDefinition":
        continue
    metadata = document.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("name"), str):
        found.add(metadata["name"])

if found != expected:
    raise SystemExit(f"CRD set mismatch: found={sorted(found)!r}")
PY
  then
    pass "Infisical Operator CRDs from secrets.infisical.com: ${expected_crds[*]}"
  else
    fail "Infisical Operator CRDs from secrets.infisical.com"
  fi

  if [[ -n "${py_bin:-}" ]] && "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

expected = {"infisical/kubernetes-operator:v0.10.32"}
found = set()


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "image" and isinstance(child, str):
                found.add(child)
            walk(child)
    elif isinstance(value, list):
        for child in value:
            walk(child)


for document in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")):
    walk(document)

if found != expected:
    raise SystemExit(f"image set mismatch: found={sorted(found)!r}")
PY
  then
    pass "Infisical Operator image pin"
  else
    fail "Infisical Operator image pin"
  fi

  if [[ -n "${py_bin:-}" ]] && "$py_bin" - "$rendered" <<'PY'
import sys
from pathlib import Path

import yaml

cluster_scoped = {
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "Namespace",
}
namespaced = {
    "Deployment",
    "Role",
    "RoleBinding",
    "Service",
    "ServiceAccount",
}

failures = []
for document in yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")):
    if not isinstance(document, dict):
        continue
    kind = document.get("kind")
    metadata = document.get("metadata") or {}
    namespace = metadata.get("namespace")
    if kind in cluster_scoped and namespace is not None:
        failures.append(f"cluster-scoped {kind}/{metadata.get('name')} has namespace")
    if kind in namespaced and namespace != "infisical-system":
        failures.append(f"namespaced {kind}/{metadata.get('name')} missing infisical-system")

if failures:
    raise SystemExit("; ".join(failures))
PY
  then
    pass "Infisical Operator scopes cluster and namespaced resources explicitly"
  else
    fail "Infisical Operator scopes cluster and namespaced resources explicitly"
  fi

  if grep -q '^namespace:' "${operator_dir}/kustomization.yaml"; then
    fail "Infisical Operator kustomization avoids namespace transformer"
  else
    pass "Infisical Operator kustomization avoids namespace transformer"
  fi

  before="$(find "$operator_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"
  set +e
  render_output="$(bash "${INFRA_DIR}/scripts/render-infisical-manifests.sh" --check 2>&1)"
  render_status=$?
  set -e
  after="$(find "$operator_dir" -type f -print0 | sort -z | xargs -0 sha256sum)"

  if [[ "$render_status" -eq 0 && "$before" == "$after" ]]; then
    pass "Infisical Operator render is byte-identical on rerun"
  else
    echo "$render_output"
    fail "Infisical Operator render is byte-identical on rerun"
  fi
}

python_bin() {
  if command -v python &>/dev/null; then
    command -v python
  elif command -v python3 &>/dev/null; then
    command -v python3
  else
    return 1
  fi
}

assert_vms_module_present() {
  for file in \
    "modules/platform-cluster-vms/main.tf" \
    "modules/platform-cluster-vms/variables.tf" \
    "modules/platform-cluster-vms/outputs.tf" \
    "modules/platform-cluster-vms/versions.tf" \
    "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl"; do
    assert_file_exists "$file"
  done
}

assert_vms_module_variables_documented() {
  local variables_file="${INFRA_DIR}/modules/platform-cluster-vms/variables.tf"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "platform-cluster-vms variables documented"
    return
  fi

  if "$PYTHON_BIN" - "$variables_file" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
expected = {
    "channel_id",
    "region",
    "vpc_id",
    "k3s_version",
    "server_count",
    "server_plan",
    "agent_count",
    "agent_plan",
    "ssh_key_ids",
    "allowed_ssh_cidrs",
    "remote_kubeconfig_path",
    "firewall_name",
}

blocks = {}
for match in re.finditer(r'variable\s+"([^"]+)"\s+\{', text):
    name = match.group(1)
    start = match.end()
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    blocks[name] = text[start:index - 1]

missing = expected - blocks.keys()
extra = blocks.keys() - expected
if missing or extra:
    raise SystemExit(f"variable set mismatch: missing={sorted(missing)} extra={sorted(extra)}")

for name in sorted(expected):
    block = blocks[name]
    if not re.search(r"^\s*type\s*=", block, re.MULTILINE):
        raise SystemExit(f"{name} missing type")
    has_default = re.search(r"^\s*default\s*=", block, re.MULTILINE) is not None
    description_match = re.search(r'^\s*description\s*=\s*"([^"]+)"', block, re.MULTILINE)
    if not description_match:
        raise SystemExit(f"{name} missing description")
    if not has_default and not description_match.group(1).endswith("no default; required"):
        raise SystemExit(f"{name} missing required-description suffix")
PY
  then
    pass "platform-cluster-vms variables documented"
  else
    fail "platform-cluster-vms variables documented"
  fi

  assert_file_contains "modules/platform-cluster-vms/outputs.tf" "sensitive = true" "platform-cluster-vms sensitive token output"
}

assert_cloud_init_template_present() {
  assert_file_exists "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl"
}

assert_cloud_init_idempotency_marker() {
  assert_file_contains "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl" "/etc/k3s-install-marker" "cloud-init idempotency marker"
}

assert_cloud_init_strict_failure() {
  assert_file_contains "modules/platform-cluster-vms/cloud-init/k3s-server.yaml.tftpl" "set -euo pipefail" "cloud-init strict shell flags"
}

assert_template_has_conditional_dispatch() {
  assert_file_contains "templates/platform-channel/main.tf" 'count  = var.cluster_target == "k3d-local"' "template dispatches k3d-local"
  assert_file_contains "templates/platform-channel/main.tf" 'count  = var.cluster_target == "vultr-vms"' "template dispatches vultr-vms"
}

assert_dev_root_present() {
  for file in \
    "roots/channels/dev/main.tf" \
    "roots/channels/dev/backend.tfbackend" \
    "roots/channels/dev/channel.auto.tfvars.json" \
    "roots/channels/dev/.terraform.lock.hcl"; do
    assert_file_exists "$file"
  done
}

assert_dev_tofu_validate() {
  local root="${INFRA_DIR}/roots/channels/dev"
  local lockfile="${root}/.terraform.lock.hcl"
  local before
  local after

  if ! command -v tofu >/dev/null 2>&1; then
    fail "dev root tofu validate"
    return
  fi

  before="$(sha256sum "$lockfile" | awk '{print $1}')"

  if tofu -chdir="$root" init -backend=false >/dev/null && tofu -chdir="$root" validate >/dev/null; then
    pass "dev root tofu init -backend=false and validate"
  else
    fail "dev root tofu init -backend=false and validate"
    return
  fi

  after="$(sha256sum "$lockfile" | awk '{print $1}')"
  if [[ "$before" == "$after" ]]; then
    pass "dev root lockfile byte-identical after re-init"
  else
    fail "dev root lockfile byte-identical after re-init"
  fi
}

assert_local_root_present() {
  for file in \
    "roots/channels/local/main.tf" \
    "roots/channels/local/backend.tfbackend" \
    "roots/channels/local/channel.auto.tfvars.json" \
    "roots/channels/local/.terraform.lock.hcl"; do
    assert_file_exists "$file"
  done
}

assert_channel_backend_drift_check() {
  local channel="$1"
  local committed="${INFRA_DIR}/roots/channels/${channel}/backend.tfbackend"
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/${channel}"
  local resolved="${tmp_dir}/resolved.json"
  local generated="${tmp_dir}/backend.tfbackend"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "${channel} backend generator drift check"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" --out "$resolved" \
    && "$PYTHON_BIN" "${INFRA_DIR}/scripts/generate_channel_backend.py" --resolved "$resolved" --out "$generated" \
    && cmp -s "$generated" "$committed"; then
    pass "${channel} backend generated artifact drift-free"
  else
    diff -u "$committed" "$generated" || true
    fail "${channel} backend generated artifact drift-free"
  fi
}

assert_channel_tfvars_drift_check() {
  local channel="$1"
  local committed="${INFRA_DIR}/roots/channels/${channel}/channel.auto.tfvars.json"
  local tmp_dir="${REPO_ROOT}/.tmp/validate-platform-bootstrap/${channel}"
  local resolved="${tmp_dir}/resolved.json"
  local generated="${tmp_dir}/channel.auto.tfvars.json"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "${channel} tfvars generator drift check"
    return
  fi

  rm -rf "$tmp_dir"
  mkdir -p "$tmp_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" --out "$resolved" \
    && "$PYTHON_BIN" "${INFRA_DIR}/scripts/generate_channel_tfvars.py" --resolved "$resolved" --out "$generated" \
    && cmp -s "$generated" "$committed"; then
    pass "${channel} tfvars generated artifact drift-free"
  else
    diff -u "$committed" "$generated" || true
    fail "${channel} tfvars generated artifact drift-free"
  fi
}

assert_local_tofu_validate() {
  local root="${INFRA_DIR}/roots/channels/local"
  local lockfile="${root}/.terraform.lock.hcl"
  local before
  local after

  if ! command -v tofu >/dev/null 2>&1; then
    fail "local root tofu validate"
    return
  fi

  before="$(sha256sum "$lockfile" | awk '{print $1}')"

  if tofu -chdir="$root" init -backend=false >/dev/null && tofu -chdir="$root" validate >/dev/null; then
    pass "local root tofu init -backend=false and validate"
  else
    fail "local root tofu init -backend=false and validate"
    return
  fi

  after="$(sha256sum "$lockfile" | awk '{print $1}')"
  if [[ "$before" == "$after" ]]; then
    pass "local root lockfile byte-identical after re-init"
  else
    fail "local root lockfile byte-identical after re-init"
  fi
}

assert_spawn_against_dev_succeeds() {
  local out_dir="${REPO_ROOT}/.tmp/test-spawn"
  local output_file="${out_dir}/channel.yaml"

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "spawn against dev succeeds"
    return
  fi

  rm -rf "$out_dir"

  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/spawn_platform_channel.py" --parent dev --suffix pr-123 --out .tmp/test-spawn \
    && [[ -f "$output_file" ]] \
    && grep -q '^id: dev-pr-123$' "$output_file" \
    && [[ ! -e "${INFRA_DIR}/channels/dev-pr-123.yaml" ]] \
    && [[ ! -e "${INFRA_DIR}/roots/channels/dev-pr-123" ]]; then
    pass "spawn against dev succeeds under .tmp only"
  else
    fail "spawn against dev succeeds under .tmp only"
  fi
}

assert_spawn_against_disabled_fails() {
  local out_dir="${REPO_ROOT}/.tmp/test-spawn-disabled"
  local output
  local status

  if ! PYTHON_BIN="$(python_bin)"; then
    fail "spawn against disabled channel fails"
    return
  fi

  rm -rf "$out_dir"
  set +e
  output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/spawn_platform_channel.py" --parent ephemeral-disabled --suffix pr-123 --out .tmp/test-spawn-disabled 2>&1)"
  status=$?
  set -e

  if [[ "$status" -ne 0 ]] && grep -q '"code": "ephemeral_children_disabled"' <<<"$output" && [[ ! -e "$out_dir/channel.yaml" ]]; then
    pass "spawn against disabled channel returns structured failure"
  else
    fail "spawn against disabled channel returns structured failure"
  fi
}

assert_install_cluster_tools_check() {
  local output
  local status

  set +e
  output="$(bash "${INFRA_DIR}/scripts/install-cluster-tools.sh" --check --no-color 2>&1)"
  status=$?
  set -e

  if [[ "$status" -eq 0 || "$status" -eq 1 ]]; then
    pass "install-cluster-tools --check runs (${output//$'\n'/; })"
  else
    fail "install-cluster-tools --check crashed (${output//$'\n'/; })"
  fi
}

assert_tool_version() {
  local tool="$1"
  local expected="$2"
  local pattern="$3"
  local raw_output
  local output
  local status

  set +e
  raw_output="$("$tool" --version 2>&1)"
  status=$?
  set -e
  output="$(sed -n '1p' <<<"$raw_output")"

  if [[ "$status" -eq 0 ]] && grep -Eq "$pattern" <<<"$output"; then
    pass "${tool} --version returns ${expected} (${output//$'\n'/; })"
  else
    fail "${tool} --version returns ${expected} (${output//$'\n'/; })"
  fi
}

assert_command_version() {
  local description="$1"
  local expected="$2"
  local pattern="$3"
  shift 3
  local raw_output
  local output
  local status

  set +e
  raw_output="$("$@" 2>&1)"
  status=$?
  set -e
  output="$(sed -n '1p' <<<"$raw_output")"

  if [[ "$status" -eq 0 ]] && grep -Eq "$pattern" <<<"$output"; then
    pass "${description} returns ${expected} (${output//$'\n'/; })"
  else
    fail "${description} returns ${expected} (${output//$'\n'/; })"
  fi
}

assert_gitops_tool_versions() {
  assert_tool_version "flux" "v2.8.6" '^flux version 2\.8\.6$'
  assert_command_version "helm version --short" "v3.20.2" '^v3\.20\.2(\+.*)?$' helm version --short
  assert_tool_version "sops" "v3.12.2" '^sops 3\.12\.2([[:space:]].*)?$'
  assert_tool_version "age" "v1.3.1" '^v1\.3\.1$'
  assert_tool_version "age-keygen" "v1.3.1" '^v1\.3\.1$'
  assert_tool_version "infisical" "infisical version 0.43.78" '^infisical version 0\.43\.78$'
  assert_tool_version "mc" "RELEASE.2025-08-13T08-35-41Z" '^mc version RELEASE\.2025-08-13T08-35-41Z([[:space:]].*)?$'
}

assert_bring_up_script_help_works() {
  if bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --help >/dev/null; then
    pass "bring-up-local-channel --help"
  else
    fail "bring-up-local-channel --help"
  fi
}

assert_delete_missing_local_cluster() {
  if ! command -v k3d >/dev/null 2>&1; then
    skip "delete-local-channel idempotence check requires k3d"
    return
  fi

  if k3d cluster get humility-local >/dev/null 2>&1; then
    skip "delete-local-channel missing-cluster check skipped because humility-local exists"
    return
  fi

  if bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local >/dev/null; then
    pass "delete-local-channel missing cluster is idempotent"
  else
    fail "delete-local-channel missing cluster is idempotent"
  fi
}

cluster_rollout_ready() {
  local kubeconfig_path="$1"
  local namespace="$2"
  local resource="$3"
  local description="$4"

  if kubectl --kubeconfig "$kubeconfig_path" -n "$namespace" rollout status "$resource" --timeout=300s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n "$namespace" get "$resource" >/dev/null; then
    pass "$description"
  else
    fail "$description"
    return 1
  fi
}

cluster_pvc_bound() {
  local kubeconfig_path="$1"
  local namespace="$2"
  local pvc="$3"
  local description="$4"
  local phase

  phase="$(kubectl --kubeconfig "$kubeconfig_path" -n "$namespace" get pvc "$pvc" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  if [[ "$phase" == "Bound" ]]; then
    pass "$description"
  else
    fail "$description"
    return 1
  fi
}

cluster_secret_key_present() {
  local kubeconfig_path="$1"
  local namespace="$2"
  local secret="$3"
  local key="$4"
  local description="$5"
  local value

  value="$(kubectl --kubeconfig "$kubeconfig_path" -n "$namespace" get secret "$secret" -o "jsonpath={.data.${key}}" 2>/dev/null || true)"
  if [[ -n "$value" ]]; then
    pass "$description"
  else
    fail "$description"
    return 1
  fi
}

cluster_wait_infisicalsecret_ready() {
  local kubeconfig_path="$1"
  local description="$2"
  local attempt
  local py_bin

  py_bin="$(python_bin)" || {
    fail "$description"
    return 1
  }

  for attempt in $(seq 1 60); do
    if kubectl --kubeconfig "$kubeconfig_path" -n infisical-sample get infisicalsecret infisical-local-sample -o json 2>/dev/null \
      | "$py_bin" -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

generation = payload.get("metadata", {}).get("generation")
for condition in payload.get("status", {}).get("conditions", []):
    if condition.get("type") not in {"secrets.infisical.com/ReadyToSyncSecrets", "Ready"}:
        continue
    if str(condition.get("status")) != "True":
        continue
    observed = condition.get("observedGeneration")
    if observed is not None and generation is not None and int(observed) != int(generation):
        continue
    raise SystemExit(0)

raise SystemExit(1)
'; then
      pass "$description"
      return 0
    fi
    sleep 3
  done

  kubectl --kubeconfig "$kubeconfig_path" -n infisical-sample get infisicalsecret infisical-local-sample -o yaml || true
  fail "$description"
  return 1
}

cluster_target_secret_synced() {
  local kubeconfig_path="$1"
  local encoded
  local decoded

  encoded="$(kubectl --kubeconfig "$kubeconfig_path" -n infisical-sample get secret infisical-local-sample -o jsonpath='{.data.INFISICAL_SAMPLE_KEY}' 2>/dev/null || true)"
  decoded="$(printf '%s' "$encoded" | base64 -d 2>/dev/null || true)"
  if [[ "$decoded" == "infisical-local-ready" ]]; then
    pass "target Secret/infisical-local-sample contains expected INFISICAL_SAMPLE_KEY"
  else
    fail "target Secret/infisical-local-sample contains expected INFISICAL_SAMPLE_KEY"
    return 1
  fi
}

assert_infisical_runtime_cluster_state() {
  local kubeconfig_path="$1"
  local phase="${2:-after bring-up}"

  echo "Infisical runtime resources ${phase}:"
  kubectl --kubeconfig "$kubeconfig_path" get infisicalsecret,secret -A | grep infisical-local-sample || true

  cluster_rollout_ready "$kubeconfig_path" infisical-system deployment/infisical-infisical-standalone-infisical "Infisical server Deployment Available (${phase})"
  cluster_rollout_ready "$kubeconfig_path" infisical-system statefulset/postgresql "Infisical Postgres Pod Ready (${phase})"
  cluster_rollout_ready "$kubeconfig_path" infisical-system statefulset/redis-master "Infisical Redis Pod Ready (${phase})"
  cluster_pvc_bound "$kubeconfig_path" infisical-system data-postgresql-0 "Postgres PVC data-postgresql-0 Bound (${phase})"
  cluster_pvc_bound "$kubeconfig_path" infisical-system redis-data-redis-master-0 "Redis PVC redis-data-redis-master-0 Bound (${phase})"
  cluster_rollout_ready "$kubeconfig_path" infisical-system deployment/infisical-opera-controller-manager "Infisical Operator Deployment Available (${phase})"
  cluster_secret_key_present "$kubeconfig_path" infisical-system infisical-server-bootstrap INFISICAL_AUTO_BOOTSTRAP_EMAIL "SOPS-bootstrapped Secret/infisical-server-bootstrap exists (${phase})"
  cluster_secret_key_present "$kubeconfig_path" infisical-system infisical-operator-auth clientId "Operator UA Secret clientId exists (${phase})"
  cluster_secret_key_present "$kubeconfig_path" infisical-system infisical-operator-auth clientSecret "Operator UA Secret clientSecret exists (${phase})"
  cluster_wait_infisicalsecret_ready "$kubeconfig_path" "Sample InfisicalSecret condition secrets.infisical.com/ReadyToSyncSecrets=True (${phase})"
  cluster_target_secret_synced "$kubeconfig_path"
}

assert_postgres_restart_durable() {
  local kubeconfig_path="$1"
  local postgres_pod

  postgres_pod="$(kubectl --kubeconfig "$kubeconfig_path" -n infisical-system get pod \
    -l app.kubernetes.io/name=postgresql,app.kubernetes.io/component=primary \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"

  if [[ -z "$postgres_pod" ]]; then
    fail "Postgres restart durability: existing Pod found"
    return
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n infisical-system delete pod "$postgres_pod" --wait=false >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n infisical-system rollout status statefulset/postgresql --timeout=300s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n infisical-system wait deployment/infisical-infisical-standalone-infisical --for=condition=Available --timeout=300s >/dev/null; then
    pass "Postgres Pod recreates after deletion"
  else
    fail "Postgres Pod recreates after deletion"
    return
  fi

  cluster_pvc_bound "$kubeconfig_path" infisical-system data-postgresql-0 "Postgres PVC remains Bound after Pod restart"
  cluster_wait_infisicalsecret_ready "$kubeconfig_path" "InfisicalSecret continues to reconcile after Postgres restart"
  cluster_target_secret_synced "$kubeconfig_path"
}

assert_local_cluster_can_create() {
  local kubeconfig_path="${HOME}/.kube/humility-local.yaml"
  local node_count
  local bring_up_output
  local second_bring_up_output
  local delete_output
  local second_delete_output
  local bring_up_status
  local second_bring_up_status
  local delete_status
  local second_delete_status
  local marker_file="${REPO_ROOT}/.tmp/gitops-source/local/gitops/channels/local/generated/gitops-snapshot-marker.yaml"
  local expected_sha
  local actual_sha
  local git_pod
  local git_snapshot_ok
  local attempt

  if ! command -v k3d >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: k3d"
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: docker"
    return
  fi
  if ! command -v kubectl >/dev/null 2>&1; then
    skip "CLUSTER: tools missing: kubectl"
    return
  fi

  if ! docker info >/dev/null 2>&1; then
    skip "CLUSTER: docker daemon unavailable"
    return
  fi

  set +e
  bring_up_output="$(bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local 2>&1)"
  bring_up_status=$?
  set -e

  if [[ "$bring_up_status" -eq 0 ]]; then
    CLUSTER_EXERCISED=1
    pass "local k3d cluster bring-up"
  else
    echo "$bring_up_output"
    fail "local k3d cluster bring-up"
    return
  fi

  if [[ -f "$kubeconfig_path" ]]; then
    pass "local kubeconfig exists"
  else
    fail "local kubeconfig exists"
  fi

  if node_count="$(kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null | awk 'NF { count += 1 } END { print count + 0 }')" && [[ "$node_count" -ge 1 ]]; then
    pass "kubectl get nodes returns ${node_count} node(s)"
  else
    fail "kubectl get nodes returns at least one node"
  fi

  if kubectl --kubeconfig "$kubeconfig_path" get nodes --no-headers 2>/dev/null | awk 'NF && $2 != "Ready" { bad = 1 } END { exit bad }'; then
    pass "kubectl get nodes reports all nodes Ready"
  else
    fail "kubectl get nodes reports all nodes Ready"
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "Flux GitRepository status=Ready"
  else
    fail "Flux GitRepository status=Ready"
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "Flux Kustomization status=Ready"
  else
    fail "Flux Kustomization status=Ready"
  fi

  echo "Flux resources after bring-up:"
  kubectl --kubeconfig "$kubeconfig_path" get gitrepository,kustomization -A || true

  assert_infisical_runtime_cluster_state "$kubeconfig_path" "after bring-up"
  assert_postgres_restart_durable "$kubeconfig_path"

  expected_sha="$(awk '/^[[:space:]]*source_sha:/ { print $2; exit }' "$marker_file" 2>/dev/null || true)"
  actual_sha="$(kubectl --kubeconfig "$kubeconfig_path" -n humility-gitops-sentinel get configmap gitops-snapshot-marker -o jsonpath='{.data.source_sha}' 2>/dev/null || true)"
  if [[ -n "$expected_sha" && "$actual_sha" == "$expected_sha" ]]; then
    pass "snapshot SHA marker reached cluster (${actual_sha})"
  else
    fail "snapshot SHA marker reached cluster"
  fi

  git_pod="$(kubectl --kubeconfig "$kubeconfig_path" -n git-system get pod -l app.kubernetes.io/name=git-daemon --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  if [[ -n "$git_pod" ]] \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system delete pod "$git_pod" --wait=false >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system rollout status deployment/git-daemon --timeout=180s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n git-system wait deployment/git-daemon --for=condition=Available --timeout=180s >/dev/null; then
    pass "git-daemon Deployment recreates Pod after deletion"
  else
    fail "git-daemon Deployment recreates Pod after deletion"
  fi

  git_snapshot_ok=0
  for attempt in $(seq 1 60); do
    git_pod="$(kubectl --kubeconfig "$kubeconfig_path" -n git-system get pod -l app.kubernetes.io/name=git-daemon --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -n "$git_pod" ]] \
      && kubectl --kubeconfig "$kubeconfig_path" -n git-system exec "$git_pod" -c git-daemon -- git --git-dir=/srv/git/humility-local.git rev-parse --verify refs/heads/main >/dev/null 2>&1; then
      git_snapshot_ok=1
      break
    fi
    sleep 2
  done

  if [[ "$git_snapshot_ok" -eq 1 ]]; then
    pass "git-daemon PVC preserves seeded snapshot after Pod restart"
  else
    fail "git-daemon PVC preserves seeded snapshot after Pod restart"
  fi

  if command -v flux >/dev/null 2>&1; then
    KUBECONFIG="$kubeconfig_path" flux reconcile source git humility-local --namespace flux-system --timeout=180s >/dev/null 2>&1 || true
    KUBECONFIG="$kubeconfig_path" flux reconcile kustomization humility-local --namespace flux-system --with-source --timeout=180s >/dev/null 2>&1 || true
  else
    kubectl --kubeconfig "$kubeconfig_path" -n flux-system annotate gitrepository/humility-local reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite >/dev/null 2>&1 || true
    kubectl --kubeconfig "$kubeconfig_path" -n flux-system annotate kustomization/humility-local reconcile.fluxcd.io/requestedAt="$(date +%s)" --overwrite >/dev/null 2>&1 || true
  fi

  if kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait gitrepository/humility-local --for=condition=Ready --timeout=180s >/dev/null \
    && kubectl --kubeconfig "$kubeconfig_path" -n flux-system wait kustomization/humility-local --for=condition=Ready --timeout=180s >/dev/null; then
    pass "git-daemon restart resilience: Flux still reconciles"
  else
    fail "git-daemon restart resilience: Flux still reconciles"
  fi

  set +e
  second_bring_up_output="$(bash "${INFRA_DIR}/scripts/bring-up-local-channel.sh" --channel local 2>&1)"
  second_bring_up_status=$?
  set -e

  if [[ "$second_bring_up_status" -eq 0 ]] && grep -q "Flux post-install complete for channel 'local'" <<<"$second_bring_up_output"; then
    pass "second bring-up reapplies Flux without error"
  else
    echo "$second_bring_up_output"
    fail "second bring-up reapplies Flux without error"
  fi

  assert_infisical_runtime_cluster_state "$kubeconfig_path" "after second bring-up"

  set +e
  delete_output="$(bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local 2>&1)"
  delete_status=$?
  set -e

  if [[ "$delete_status" -eq 0 ]]; then
    pass "local k3d cluster cleanup"
  else
    echo "$delete_output"
    fail "local k3d cluster cleanup"
  fi

  if ! k3d cluster get humility-local >/dev/null 2>&1; then
    pass "local k3d cluster gone after cleanup"
  else
    fail "local k3d cluster gone after cleanup"
  fi

  set +e
  second_delete_output="$(bash "${INFRA_DIR}/scripts/delete-local-channel.sh" --channel local 2>&1)"
  second_delete_status=$?
  set -e

  if [[ "$second_delete_status" -eq 0 ]] && grep -q "already gone" <<<"$second_delete_output"; then
    pass "second delete is an idempotent no-op"
  else
    echo "$second_delete_output"
    fail "second delete is an idempotent no-op"
  fi
}

echo "=== Slice 101.01 channel contract validation ==="

for file in \
  "schemas/platform-channel.schema.json" \
  "schemas/platform-channel-resolved.schema.json" \
  "channels/local.yaml" \
  "channels/dev.yaml" \
  "channels/fixtures/local-child.yaml" \
  "channels/fixtures/dev-child.yaml" \
  "channels/fixtures/ephemeral-disabled.yaml" \
  "channels/fixtures/missing-parent.yaml" \
  "channels/fixtures/circular-a.yaml" \
  "channels/fixtures/circular-b.yaml" \
  "scripts/resolve_platform_channel.py" \
  "scripts/validate_platform_channels.py"; do
  assert_file_exists "$file"
done

for path in \
  "environments" \
  "modules/platform-cluster/main.tf" \
  "channels/customer.yaml" \
  "channels/internal.yaml" \
  "channels/e2e.yaml"; do
  assert_path_absent "$path"
done

if PYTHON_BIN="$(python_bin)"; then
  if "$PYTHON_BIN" "${INFRA_DIR}/scripts/validate_platform_channels.py"; then
    pass "platform channel validator"
  else
    fail "platform channel validator"
  fi

  for channel in local dev local-child; do
    if "$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel "$channel" >/dev/null; then
      pass "resolve: ${channel}"
    else
      fail "resolve: ${channel}"
    fi
  done

  missing_parent_output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel missing-parent 2>&1 >/dev/null || true)"
  if grep -q '"code": "missing_parent"' <<<"$missing_parent_output"; then
    pass "missing-parent reports missing_parent"
  else
    fail "missing-parent reports missing_parent"
  fi

  circular_output="$("$PYTHON_BIN" "${INFRA_DIR}/scripts/resolve_platform_channel.py" --channel circular-a 2>&1 >/dev/null || true)"
  if grep -q '"code": "circular_parent"' <<<"$circular_output"; then
    pass "circular-a reports circular_parent"
  else
    fail "circular-a reports circular_parent"
  fi
else
  fail "python interpreter available"
fi

echo ""
echo "=== Slice 101.02 local k3d cluster validation ==="

for file in \
  "modules/platform-cluster-k3d/main.tf" \
  "modules/platform-cluster-k3d/variables.tf" \
  "modules/platform-cluster-k3d/outputs.tf" \
  "modules/platform-cluster-k3d/versions.tf" \
  "scripts/install-cluster-tools.sh" \
  "scripts/bring-up-local-channel.sh" \
  "scripts/install-flux-for-channel.sh" \
  "scripts/delete-local-channel.sh"; do
  assert_file_exists "$file"
done

assert_dir_exists "modules/platform-cluster-k3d"
assert_executable "scripts/install-cluster-tools.sh"
assert_executable "scripts/bring-up-local-channel.sh"
assert_executable "scripts/install-flux-for-channel.sh"
assert_executable "scripts/delete-local-channel.sh"
assert_install_cluster_tools_check
assert_gitops_tool_versions
assert_bring_up_script_help_works
assert_delete_missing_local_cluster

echo ""
echo "=== Slice 102.02 GitOps layout and Flux lockfile validation ==="

assert_gitops_flux_components
assert_repo_path_absent "k8s"
assert_repo_file_exists "gitops/sources/local/git-daemon.yaml"
assert_file_exists "scripts/render-gitops-source.py"
assert_executable "scripts/render-gitops-source.py"
assert_gitops_channel_schema_rendering

echo ""
echo "=== Slice 103.02 Infisical server raw manifest validation ==="

assert_infisical_server_raw_manifests

echo ""
echo "=== Slice 103.03 Infisical Operator raw manifest validation ==="

assert_infisical_operator_raw_manifests

echo ""
echo "=== Slice 102.03 SOPS+age bootstrap sentinel validation ==="

assert_sops_bootstrap_boundary

echo ""
echo "=== Slice 103.04 Infisical identity bootstrap validation ==="

assert_infisical_identity_bootstrap_script

echo ""
echo "=== Slice 103.05 Infisical channel schema and sample validation ==="

assert_infisical_channel_schema_and_sample

echo ""
echo "=== Slice 104.01 object-storage channel schema validation ==="

assert_object_storage_channel_schema

echo ""
echo "=== Slice 104.03 Infisical storage bootstrap validation ==="

assert_object_storage_infisical_bootstrap

echo ""
echo "=== Slice 104.04 raw MinIO manifest validation ==="

assert_object_storage_minio_manifests

echo ""
echo "=== Slice 104.05 bucket Job manifest validation ==="

assert_object_storage_bucket_job

if [[ "$RUN_CLUSTER" -eq 1 ]]; then
  assert_local_cluster_can_create
else
  skip "CLUSTER: not requested; pass --cluster to create and verify local k3d"
fi

echo ""
echo "=== Slice 101.03 remote Vultr VM plan-surface validation ==="

assert_vms_module_present
assert_vms_module_variables_documented
assert_cloud_init_template_present
assert_cloud_init_idempotency_marker
assert_cloud_init_strict_failure
assert_template_has_conditional_dispatch
assert_dev_root_present
assert_dev_tofu_validate

echo ""
echo "=== Slice 101.04 channel template and generated root validation ==="

for file in \
  "scripts/generate_channel_backend.py" \
  "scripts/generate_channel_tfvars.py" \
  "scripts/spawn_platform_channel.py"; do
  assert_file_exists "$file"
  assert_executable "$file"
done

assert_local_root_present
assert_channel_backend_drift_check "dev"
assert_channel_tfvars_drift_check "dev"
assert_channel_backend_drift_check "local"
assert_channel_tfvars_drift_check "local"
assert_local_tofu_validate
assert_spawn_against_dev_succeeds
assert_spawn_against_disabled_fails

echo ""
echo "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
if [[ "$CLUSTER_EXERCISED" -eq 1 ]]; then
  echo "Cluster mode exercised: yes"
else
  echo "Cluster mode exercised: no"
fi

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
