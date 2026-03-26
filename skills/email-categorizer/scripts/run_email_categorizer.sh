#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

exec python3 -m email_categorizer \
  --account "${PROJECT_ROOT}/config/account.toml" \
  --rules "${PROJECT_ROOT}/config/rules.toml" \
  "$@"
