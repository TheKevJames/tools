FROM docker.io/library/caddy:2.7.5-builder-alpine AS builder

RUN xcaddy build \
    --with github.com/greenpau/caddy-security@v1.1.22


FROM docker.io/library/caddy:2.7.5-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
