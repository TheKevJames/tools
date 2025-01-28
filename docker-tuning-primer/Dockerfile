# syntax=docker/dockerfile:1

# https://pkgs.alpinelinux.org/packages?name=&branch=v3.21&repo=&arch=&maintainer=
# renovate: datasource=repology depName=alpine_3_21/bc versioning=loose
ARG BC_VERSION=1.07.1-r5
# renovate: datasource=repology depName=alpine_3_21/mysql versioning=loose
ARG MYSQL_VERSION=11.4.4-r1
# renovate: datasource=repology depName=alpine_3_21/mysql-client versioning=loose
ARG MYSQLCLIENT_VERSION=11.4.4-r1
# renovate: datasource=repology depName=alpine_3_21/ncurses versioning=loose
ARG NCURSES_VERSION=6.5_p20241006-r3
# renovate: datasource=repology depName=alpine_3_21/socat versioning=loose
ARG SOCAT_VERSION=1.8.0.1-r0


FROM alpine:3.21.2

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
