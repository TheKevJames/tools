# syntax=docker/dockerfile:1

# renovate: datasource=github-releases depName=greenpau/caddy-security
ARG CADDYSECURITY_VERSION=v1.1.29


FROM docker.io/library/caddy:2.8.4-builder-alpine AS builder

ARG CADDYSECURITY_VERSION
RUN xcaddy build \
    --with "github.com/greenpau/caddy-security@${CADDYSECURITY_VERSION}"


FROM docker.io/library/caddy:2.8.4-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
