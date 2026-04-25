#!/usr/bin/env bash
set -euo pipefail

# bootstrap-flux.sh - set up local age key + later bring up kind + bootstrap Flux.
#
# SLICE-034 ships the age-key portion. SLICE-035 extends this script with
# control-cluster bootstrap.

readonly AGE_KEY_DIR="${AGE_KEY_DIR:-${HOME}/.config/sops/age}"
readonly DEV_AGE_KEY="${AGE_KEY_DIR}/dev.txt"

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

main() {
  ensure_age_installed
  ensure_dev_age_key
  echo
  echo "Next: SLICE-035 will extend this script to bring up a kind cluster and bootstrap Flux."
}

main "$@"
