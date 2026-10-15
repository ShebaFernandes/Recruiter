#!/usr/bin/env bash
# Restores ONLY into a new scratch database. Never overwrites enter or uses --clean.
set -euo pipefail
umask 077
cd "${ENTER_REPO_DIR:?Set ENTER_REPO_DIR}"
: "${ENTER_BACKUP_BUCKET:?Set the approved private backup bucket}"
: "${ENTER_BACKUP_KEY:?Set the exact backup object key}"
: "${ENTER_RESTORE_DB:?Use restore_check_ followed by lowercase letters/numbers}"
[[ "$ENTER_RESTORE_DB" =~ ^restore_check_[a-z0-9_]+$ ]] || { echo 'Unsafe restore target'; exit 1; }
[[ "$ENTER_BACKUP_KEY" =~ ^postgres/[a-zA-Z0-9/._-]+\.dump$ ]] || { echo 'Invalid backup key'; exit 1; }
restore_file=$(mktemp /tmp/enter-restore.XXXXXXXX.dump)
trap 'rm -f -- "$restore_file"' EXIT
compose=(docker compose --env-file .env.production -f compose.production.yaml)
aws s3 cp "s3://${ENTER_BACKUP_BUCKET}/${ENTER_BACKUP_KEY}" "$restore_file" --only-show-errors
"${compose[@]}" exec -T db pg_restore --list < "$restore_file" >/dev/null
# createdb fails if target exists, protecting any existing restore or production data.
"${compose[@]}" exec -T db createdb -U enter "$ENTER_RESTORE_DB"
"${compose[@]}" exec -T db pg_restore -U enter --dbname="$ENTER_RESTORE_DB" --no-owner --exit-on-error < "$restore_file"
"${compose[@]}" exec -T db psql -U enter -d "$ENTER_RESTORE_DB" -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS migrations FROM django_migrations;'
echo 'Restore completed in scratch database; validate counts and application access before recovery.'
