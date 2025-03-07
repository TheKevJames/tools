# syntax=docker/dockerfile:1

# https://pkgs.alpinelinux.org/packages?name=&branch=v3.21&repo=&arch=&maintainer=
# renovate: datasource=repology depName=alpine_3_21/bc versioning=loose
ARG BC_VERSION=1.07.1-r5
# renovate: datasource=repology depName=alpine_3_21/mariadb versioning=loose
ARG MARIADB_VERSION=11.4.5-r0
# renovate: datasource=repology depName=alpine_3_21/mariadb-client versioning=loose
ARG MARIADBCLIENT_VERSION=11.4.5-r0
# renovate: datasource=repology depName=alpine_3_21/ncurses versioning=loose
ARG NCURSES_VERSION=6.5_p20241006-r3
# renovate: datasource=repology depName=alpine_3_21/socat versioning=loose
ARG SOCAT_VERSION=1.8.0.1-r0


FROM alpine:3.21.3

ARG BC_VERSION
ARG MARIADB_VERSION
ARG MARIADBCLIENT_VERSION
ARG NCURSES_VERSION
ARG SOCAT_VERSION
RUN --mount=type=cache,target=/var/cache/apk \
    apk add --no-progress \
        "bc=${BC_VERSION}" \
        "mariadb=${MARIADB_VERSION}" \
        "mariadb-client=${MARIADBCLIENT_VERSION}" \
        "ncurses=${NCURSES_VERSION}" \
        "socat=${SOCAT_VERSION}"

COPY root /

ENV TERM=rxvt

ENTRYPOINT [ "/tuning-primer-wrapper.sh" ]
