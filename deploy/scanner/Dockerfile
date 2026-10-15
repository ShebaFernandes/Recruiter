# Keep only the signed signature bundle from upstream, not its affected libraries.
FROM clamav/clamav@sha256:638d90201ee7ee6a82d249a2fc23b132e578673b5f1f2766852b127676ca1ef6 AS signatures
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       clamav clamav-daemon clamav-freshclam clamdscan ca-certificates util-linux tini \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libxml2)" ge '2.9.14+dfsg-1.3ubuntu3.9' \
    && rm -rf /var/lib/apt/lists/*
COPY --from=signatures /var/lib/clamav/ /opt/clamav-seed/
COPY clamd.conf freshclam.conf /etc/clamav/
COPY --chmod=755 entrypoint.sh /usr/local/bin/scanner-entrypoint
EXPOSE 3310
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/scanner-entrypoint"]
HEALTHCHECK --interval=30s --timeout=15s --start-period=5m CMD clamdscan --ping=3 || exit 1
