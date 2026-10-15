#!/usr/bin/env bash
set -euo pipefail
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
compose=(docker compose --env-file .env.production -f compose.production.yaml)
failed=0
if systemctl is-failed --quiet enter-backup.service; then failed=1; fi
"${compose[@]}" exec -T backend python manage.py check_resume_operations || failed=1
"${compose[@]}" exec -T scanner clamdscan --ping=3 || failed=1
if [[ "$failed" == 1 ]]; then
  # SNS is optional; set a confirmed operator topic, never a candidate recipient.
  if [[ -n "${ENTER_ALERT_TOPIC_ARN:-}" ]]; then
    aws sns publish --topic-arn "$ENTER_ALERT_TOPIC_ARN" \
      --subject 'ENTER operations need attention' \
      --message 'Worker, queue, cleanup or scanner check failed. Inspect private operational logs.' >/dev/null
  fi
  exit 1
fi
