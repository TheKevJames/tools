# syntax=docker/dockerfile:1

# renovate: datasource=pypi depName=poetry
ARG POETRY_VERSION=2.3.1
# renovate: datasource=pypi depName=poetry-plugin-export
ARG POETRYPLUGINEXPORT_VERSION=1.10.0
# renovate: datasource=github-releases depName=eficode/wait-for
ARG WAITFOR_VERSION=2.2.4


FROM curlimages/curl:8.18.0 AS fetcher

ARG WAITFOR_VERSION
RUN curl -vsSLo /tmp/wait-for "https://github.com/eficode/wait-for/releases/download/v${WAITFOR_VERSION}/wait-for" && \
    chmod +x /tmp/wait-for


FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:553.0.0-emulators AS base

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

ARG TARGETPLATFORM

# TODO: figure out how to properly pin these versions and have renovate update them
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt,id=apt-cache-$TARGETPLATFORM \
    --mount=type=cache,sharing=locked,target=/var/lib/apt,id=apt-lib-$TARGETPLATFORM \
    apt-get install -qy --no-install-recommends \
        "python3-venv" && \
    python3 -m venv /opt/poetry

ARG POETRY_VERSION
ARG POETRYPLUGINEXPORT_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/poetry/bin/pip install \
        "poetry==${POETRY_VERSION}" \
        "poetry-plugin-export==${POETRYPLUGINEXPORT_VERSION}" && \
    /opt/poetry/bin/poetry config virtualenvs.options.no-pip true

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN /opt/poetry/bin/poetry export -f requirements.txt --output /tmp/requirements.txt


FROM base

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r /tmp/requirements.txt --break-system-packages

COPY --from=fetcher /tmp/wait-for /usr/bin
COPY --link pubsubc.py /usr/bin/pubsubc
COPY --link run /usr/bin/run

EXPOSE 8681 8682/udp

ENTRYPOINT ["/usr/bin/run"]
