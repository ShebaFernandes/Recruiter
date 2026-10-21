#!/usr/bin/env bash
set -euo pipefail
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
compose=(docker compose --env-file .env.production -f compose.production.yaml)
failed=0
: "${ENTER_BACKUP_STATE_FILE:?Set verified backup marker path}"
: "${ENTER_HTTPS_URL:?Set approved HTTPS readiness URL}"
: "${ENTER_ALERT_TOPIC_ARN:?Set confirmed operator alert topic}"
[[ "$ENTER_HTTPS_URL" == https://* ]] || exit 1
if systemctl is-failed --quiet enter-backup.service; then failed=1; fi
if systemctl is-failed --quiet enter-backup-daily.service; then failed=1; fi
python3 - <<'PY' || failed=1
import json, os, shutil, time
from pathlib import Path
state = json.loads(Path(os.environ['ENTER_BACKUP_STATE_FILE']).read_text())
assert 0 <= time.time() - state['verified_at'] <= 7200, 'Backup is stale'
disk = shutil.disk_usage(os.environ['ENTER_REPO_DIR'])
assert disk.used / disk.total < .80, 'Disk usage >= 80%'
PY
curl --fail --silent --show-error --max-time 15 "$ENTER_HTTPS_URL" >/dev/null || failed=1
"${compose[@]}" exec -T db pg_isready -U enter -d enter >/dev/null || failed=1
"${compose[@]}" exec -T backend python manage.py check_resume_operations || failed=1
"${compose[@]}" exec -T scanner clamdscan --ping=3 || failed=1
if [[ "$failed" == 1 ]]; then
  # SNS is optional; set a confirmed operator topic, never a candidate recipient.
  if [[ -n "${ENTER_ALERT_TOPIC_ARN:-}" ]]; then
    aws sns publish --topic-arn "$ENTER_ALERT_TOPIC_ARN" \
      --subject 'ENTER operations need attention' \
      --message 'ENTER health, backup freshness, disk, queue, worker or scanner check failed. Inspect private operational logs.' >/dev/null
  fi
  exit 1
fi
