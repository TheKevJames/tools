FROM docker.io/library/caddy:2.7.6-builder-alpine AS builder

RUN xcaddy build \
    --with github.com/greenpau/caddy-security@v1.1.23


FROM docker.io/library/caddy:2.7.6-alpine

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
