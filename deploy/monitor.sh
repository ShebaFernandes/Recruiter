#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
exec flock -n /run/lock/enter-monitor.lock python3 "${ENTER_OPS_DIR:-deploy}/monitor_safe.py"
