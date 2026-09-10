# syntax=docker/dockerfile:1

# renovate: datasource=pypi depName=prometheus-client
ARG PROMETHEUSCLIENT_VERSION=0.26.0
# renovate: datasource=pypi depName=pybluez
ARG PYBLUEZ_VERSION=0.23


# TODO: update to newer python
FROM python:3.9.22-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-emit-project --no-dev -o /tmp/requirements.txt


# TODO: update to a newer python
FROM python:3.9.22-slim

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
# TODO: figure out which other deps we need, add them, then do --no-install-recommends
# TODO: figure out how to properly pin these versions and have renovate update them
# hadolint ignore=DL3015
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -qy && \
    apt-get upgrade -qy && \
    apt-get install -qy \
        "bluetooth" \
        "libbluetooth-dev" \
        "libglib2.0-dev" \
        "python3-pip"

# TODO: use the builder link once the dep chain is fixed
# COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
# python3 -m pip install -r /tmp/requirements.txt --break-system-packages

# TODO: update to solve the below note, or consider using bleak or bless
# pybluez won't compile with the newer version of setuptools so use fixed
# version
ARG PROMETHEUSCLIENT_VERSION
ARG PYBLUEZ_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade setuptools==57.5.0 && \
    python3 -m pip install \
        "prometheus-client==${PROMETHEUSCLIENT_VERSION}" \
        "pybluez==${PYBLUEZ_VERSION}"

COPY ./atc1441_exporter /app

ENTRYPOINT ["python3", "-m", "app.main"]
