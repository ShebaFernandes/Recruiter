#!/bin/bash
set -euo pipefail

if [ "$(id -u)" = 0 ]; then
    mkdir -p /var/lib/clamav /run/clamav
    # Populate a new persistent volume, never overwrite downloaded signatures.
    for seed in /opt/clamav-seed/*.cvd /opt/clamav-seed/*.cld; do
        [ -f "$seed" ] || continue
        name=$(basename "$seed")
        stem=${name%.*}
        if [ ! -f "/var/lib/clamav/$stem.cvd" ] && [ ! -f "/var/lib/clamav/$stem.cld" ]; then
            cp "$seed" /var/lib/clamav/
        fi
    done
    chown -R clamav:clamav /var/lib/clamav
    chown clamav:clamav /run/clamav
    exec setpriv --reuid=clamav --regid=clamav --init-groups "$0"
fi

clamd --config-file=/etc/clamav/clamd.conf &
scanner=$!
# Wait for the socket so FreshClam's first successful update can notify clamd.
ready=false
for ((attempt=0; attempt<120; attempt++)); do
    if ! kill -0 "$scanner" 2>/dev/null; then
        wait "$scanner" || true
        exit 1
    fi
    if clamdscan --ping=1 >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [ "$ready" != true ]; then
    kill -TERM "$scanner" 2>/dev/null || true
    wait "$scanner" || true
    exit 1
fi
freshclam --daemon --stdout --config-file=/etc/clamav/freshclam.conf &
updater=$!
stop() {
    kill -TERM "$scanner" "$updater" 2>/dev/null || true
    wait "$scanner" "$updater" 2>/dev/null || true
}
trap 'stop; exit 0' TERM INT
# A dead scanner OR updater terminates the container; Compose restarts it.
set +e
wait -n "$scanner" "$updater"
status=$?
stop
[ "$status" -ne 0 ] || status=1
exit "$status"
