#!/usr/bin/env bash
set -euo pipefail
# Each backup is downloaded and restored OFFLINE in an isolated capped container.
# Never create a scratch database inside the live database container.
exec bash "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}/deploy/backup.sh"
