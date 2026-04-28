#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
source "${REPO_ROOT}/infra/tests/e2e/lib/assertions.sh"
source "${REPO_ROOT}/infra/tests/fixtures/sops/bootstrap-sentinel-contract.env"
e2e_init "03-sops-bootstrap" "SOPS age bootstrap sentinel"

require_command python3
python3 - "${REPO_ROOT}/${SOPS_ENCRYPTED_SENTINEL_FIXTURE}" "${REPO_ROOT}/${SOPS_PLAINTEXT_LEAK_FIXTURE}" <<'PY'
import re
import sys
from pathlib import Path

encrypted_path = Path(sys.argv[1])
plaintext_path = Path(sys.argv[2])
encrypted = encrypted_path.read_text()
plaintext = plaintext_path.read_text()

if "sops:" not in encrypted or "encrypted_regex:" not in encrypted:
    raise SystemExit(f"{encrypted_path} is missing SOPS metadata")
if not re.search(r"(?m)^\s+[A-Za-z0-9_.-]+:\s+ENC\[", encrypted):
    raise SystemExit(f"{encrypted_path} does not keep secret values encrypted")
if "sops:" in plaintext or "ENC[" in plaintext:
    raise SystemExit(f"{plaintext_path} is not a plaintext leak fixture")
if not re.search(r"(?m)^stringData:\n(?:\s{2,}.+\n)+", plaintext):
    raise SystemExit(f"{plaintext_path} does not exercise plaintext stringData")
PY
e2e_pass "SOPS boundary fixtures distinguish encrypted and plaintext secret data"

require_cluster
escaped_sops_key="${SOPS_AGE_SECRET_KEY//./\\.}"
kubectl_cmd -n "$SOPS_AGE_SECRET_NAMESPACE" get secret "$SOPS_AGE_SECRET_NAME" -o "jsonpath={.data.${escaped_sops_key}}" | grep -q . \
  || e2e_fail "Secret/${SOPS_AGE_SECRET_NAME} missing ${SOPS_AGE_SECRET_KEY}"
e2e_pass "Flux SOPS age Secret exists"

kubectl_cmd -n "$SOPS_BOOTSTRAP_SENTINEL_NAMESPACE" get secret "$SOPS_BOOTSTRAP_SENTINEL_SECRET" -o "jsonpath={.data.${SOPS_BOOTSTRAP_SENTINEL_KEY}}" | base64 -d \
  | tee "$(e2e_log_path bootstrap-sentinel)" | grep -q "$SOPS_BOOTSTRAP_SENTINEL_EXPECTED_VALUE" \
  || e2e_fail "${SOPS_BOOTSTRAP_SENTINEL_SECRET} Secret did not decrypt to expected value"
e2e_pass "encrypted sentinel reconciled and decrypted"
e2e_finish
