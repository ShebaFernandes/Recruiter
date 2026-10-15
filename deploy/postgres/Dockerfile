FROM postgres:17@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3 AS upstream
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 AS key
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl --fail --location https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /pgdg.asc \
    && gpg --show-keys --with-colons /pgdg.asc | grep -q 'B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8'

FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55
COPY --from=key /pgdg.asc /usr/share/keyrings/pgdg.asc
COPY pgdg.sources /etc/apt/sources.list.d/pgdg.sources
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates postgresql-common locales util-linux zstd xz-utils \
    && echo 'create_main_cluster = false' >> /etc/postgresql-common/createcluster.conf \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-17 postgresql-client-17 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libxml2)" ge '2.9.14+dfsg-1.3ubuntu3.9' \
    && localedef -i en_US -c -f UTF-8 en_US.UTF-8 \
    && sed -ri "s/^#?(listen_addresses)[[:space:]]*=.*/\1 = '*'/" /usr/share/postgresql/17/postgresql.conf.sample \
    && mkdir -p /docker-entrypoint-initdb.d /var/lib/postgresql/data /var/run/postgresql \
    && chown -R postgres:postgres /var/lib/postgresql /var/run/postgresql \
    && chmod 3777 /var/run/postgresql \
    && rm -rf /var/lib/apt/lists/*
COPY --from=upstream /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Preserve the official initialization flow without its vulnerable Go helper.
RUN grep -q 'exec gosu postgres' /usr/local/bin/docker-entrypoint.sh \
    && sed -i 's/exec gosu postgres/exec setpriv --reuid=postgres --regid=postgres --init-groups/' /usr/local/bin/docker-entrypoint.sh
ENV PG_MAJOR=17 PGDATA=/var/lib/postgresql/data LANG=en_US.utf8 PATH=/usr/lib/postgresql/17/bin:$PATH
VOLUME /var/lib/postgresql/data
EXPOSE 5432
STOPSIGNAL SIGINT
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
