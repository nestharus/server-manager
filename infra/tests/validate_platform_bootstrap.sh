#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"

PASS_COUNT=0
FAIL_COUNT=0

pass() {
  echo "  PASS: $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  echo "  FAIL: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

assert_file_exists() {
  local file="$1"
  if [[ -f "${INFRA_DIR}/${file}" ]]; then
    pass "exists: ${file}"
  else
    fail "missing: ${file}"
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

python_bin() {
  if command -v python &>/dev/null; then
    command -v python
  elif command -v python3 &>/dev/null; then
    command -v python3
  else
    return 1
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
echo "Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
