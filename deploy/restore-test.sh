#!/usr/bin/env bash
set -euo pipefail
# Select an independently approved historical object and recorded checksum.
: "${ENTER_RESTORE_KEY:?Select an approved older hourly/daily backup key}"
: "${ENTER_RESTORE_SHA256:?Supply the previously recorded SHA256}"
exec bash "${ENTER_OPS_DIR:-${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}/deploy}/backup.sh"
