# syntax=docker/dockerfile:1

# renovate: datasource=repology depName=debian_12/bluetooth versioning=loose
ARG BLUETOOTH_VERSION=5.66-1+deb12u2
# renovate: datasource=repology depName=debian_12/libbluetooth-dev versioning=loose
ARG LIBBLUETOOTHDEV_VERSION=5.66-1+deb12u2
# renovate: datasource=repology depName=debian_12/libglib2.0-dev versioning=loose
ARG LIBGLIB20DEV_VERSION=2.74.6-2+deb12u5
# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=25.1.1
# renovate: datasource=pypi depName=poetry
ARG POETRY_VERSION=2.1.3
# renovate: datasource=pypi depName=poetry-plugin-export
ARG POETRYPLUGINEXPORT_VERSION=1.9.0
# renovate: datasource=pypi depName=prometheus-client
ARG PROMETHEUSCLIENT_VERSION=0.22.0
# renovate: datasource=pypi depName=pybluez
ARG PYBLUEZ_VERSION=0.23
# renovate: datasource=repology depName=debian_12/python3-pip versioning=loose
ARG PYTHON3PIP_VERSION=23.0.1+dfsg-1


# TODO: update to newer python
FROM python:3.9.22-slim AS builder

RUN python3 -m venv /opt/poetry

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/poetry/bin/pip install --upgrade "pip==${PIP_VERSION}"

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


# TODO: update to a newer python
FROM python:3.9.22-slim

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
# TODO: pin me
# TODO: figure out which other deps we need, add them, then do --no-install-recommends
ARG BLUETOOTH_VERSION
ARG LIBBLUETOOTHDEV_VERSION
ARG LIBGLIB20DEV_VERSION
ARG PYTHON3PIP_VERSION
# hadolint ignore=DL3015
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update -qy && \
    apt-get upgrade -qy && \
    apt-get install -qy \
        "bluetooth=${BLUETOOTH_VERSION}" \
        "libbluetooth-dev=${LIBBLUETOOTHDEV_VERSION}" \
        "libglib2.0-dev=${LIBGLIB20DEV_VERSION}" \
        "python3-pip=${PYTHON3PIP_VERSION}"

# TODO: use the builder link once the dep chain is fixed
# COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
# python3 -m pip install -r /tmp/requirements.txt --break-system-packages

# TODO: update to solve the below note, or consider using bleak or bless
# pybluez wont compile with the newer version of setuptools so use fixed version
ARG PROMETHEUSCLIENT_VERSION
ARG PYBLUEZ_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade setuptools==57.5.0 && \
    python3 -m pip install \
        "prometheus-client==${PROMETHEUSCLIENT_VERSION}" \
        "pybluez==${PYBLUEZ_VERSION}"

COPY ./atc1441_exporter /app

ENTRYPOINT ["python3", "-m", "app.main"]
