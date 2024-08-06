# syntax=docker/dockerfile:1

# renovate: datasource=repology depName=alpine_3_20/bc versioning=loose
ARG BC_VERSION=1.07.1-r4
# renovate: datasource=repology depName=alpine_3_20/mysql versioning=loose
ARG MYSQL_VERSION=10.11.6-r0
# renovate: datasource=repology depName=alpine_3_20/mysql-client versioning=loose
ARG MYSQLCLIENT_VERSION=10.11.6-r0
# renovate: datasource=repology depName=alpine_3_20/ncurses versioning=loose
ARG NCURSES_VERSION=6.4_p20231125-r0
# renovate: datasource=repology depName=alpine_3_20/socat versioning=loose
ARG SOCAT_VERSION=1.8.0.0-r0


FROM alpine:3.20.2

ARG BC_VERSION
ARG MYSQL_VERSION
ARG MYSQLCLIENT_VERSION
ARG NCURSES_VERSION
ARG SOCAT_VERSION
RUN --mount=type=cache,target=/var/cache/apk \
    apk add --no-progress \
        "bc=${BC_VERSION}" \
        "mysql=${MYSQL_VERSION}" \
        "mysql-client=${MYSQLCLIENT_VERSION}" \
        "ncurses=${NCURSES_VERSION}" \
        "socat=${SOCAT_VERSION}"

COPY root /

ENV TERM=rxvt

ENTRYPOINT [ "/tuning-primer-wrapper.sh" ]
