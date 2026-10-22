#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
# Lock prevents overlapping hourly/daily restore tests. Failure is monitored.
exec flock -n /run/lock/enter-backup.lock python3 "${ENTER_OPS_DIR:-deploy}/backup_safe.py"
