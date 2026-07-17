# syntax=docker/dockerfile:1

# renovate: datasource=github-releases depName=greenpau/caddy-security
ARG CADDYSECURITY_VERSION=v1.1.64


FROM --platform=$BUILDPLATFORM docker.io/library/caddy:2.11.4-builder-alpine AS builder

ARG TARGETOS
ARG TARGETARCH
ARG CADDYSECURITY_VERSION
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH GOTOOLCHAIN=auto xcaddy build \
    --with "github.com/greenpau/caddy-security@${CADDYSECURITY_VERSION}"


FROM docker.io/library/caddy:2.11.4-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
