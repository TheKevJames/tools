# syntax=docker/dockerfile:1

# renovate: datasource=github-releases depName=eficode/wait-for
ARG WAITFOR_VERSION=2.2.4


FROM curlimages/curl:8.22.0 AS fetcher

ARG WAITFOR_VERSION
RUN curl -vsSLo /tmp/wait-for "https://github.com/eficode/wait-for/releases/download/v${WAITFOR_VERSION}/wait-for" && \
    chmod +x /tmp/wait-for


FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:584.0.0-emulators AS base

ARG TARGETPLATFORM

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
# TODO: figure out how to properly pin these versions and have renovate update them
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt,id=apt-cache-$TARGETPLATFORM \
    --mount=type=cache,sharing=locked,target=/var/lib/apt,id=apt-lib-$TARGETPLATFORM \
    apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        "netcat-openbsd" \
        "python3-pip" && \
    gcloud config set disable_usage_reporting true


FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-emit-project --no-dev -o /tmp/requirements.txt


FROM base

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r /tmp/requirements.txt --break-system-packages

COPY --from=fetcher /tmp/wait-for /usr/bin
COPY --link pubsubc.py /usr/bin/pubsubc
COPY --link run /usr/bin/run

EXPOSE 8681 8682/udp

ENTRYPOINT ["/usr/bin/run"]
