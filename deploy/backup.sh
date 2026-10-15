#!/usr/bin/env bash
# Host-side timer, using the EC2 role. No credentials in command arguments or logs.
set -euo pipefail
umask 077
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
: "${ENTER_BACKUP_BUCKET:?Set a private backup bucket}"
command -v aws >/dev/null
command -v docker >/dev/null
backup_file=$(mktemp /tmp/enter-backup.XXXXXXXX.dump)
trap 'rm -f -- "$backup_file"' EXIT
compose=(docker compose --env-file .env.production -f compose.production.yaml)
"${compose[@]}" exec -T db pg_dump -U enter -d enter --format=custom --no-owner > "$backup_file"
# Validate the archive before uploading. pipefail prevents partial dumps being accepted.
"${compose[@]}" exec -T db pg_restore --list < "$backup_file" >/dev/null
backup_key="postgres/$(date -u +%Y/%m/%d/%H%M%S).dump"
aws s3 cp "$backup_file" "s3://${ENTER_BACKUP_BUCKET}/${backup_key}" --sse AES256 --only-show-errors
printf 'Database backup completed: %s\n' "$backup_key"
