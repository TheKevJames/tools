FROM docker.io/library/caddy:2.6.4-builder-alpine AS builder

RUN xcaddy build \
    --with github.com/greenpau/caddy-security@v1.1.19


FROM docker.io/library/caddy:2.6.4-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
