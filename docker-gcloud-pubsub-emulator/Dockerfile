# syntax=docker/dockerfile:1

# renovate: datasource=repology depName=debian_11/netcat-openbsd versioning=loose
ARG NETCATOPENBSD_VERSION=1.217-3
# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=23.3.2
# renovate: datasource=pypi depName=poetry
ARG POETRY_VERSION=1.8.1
# renovate: datasource=github-releases depName=eficode/wait-for
ARG WAITFOR_VERSION=2.2.4


FROM curlimages/curl:8.6.0 as fetcher

ARG WAITFOR_VERSION
RUN curl -vsSLo /tmp/wait-for "https://github.com/eficode/wait-for/releases/download/v${WAITFOR_VERSION}/wait-for" && \
    chmod +x /tmp/wait-for


# N.B. match to the python3 version in the gcloud image
FROM python:3.9.2 AS builder

RUN python3 -m venv /opt/poetry

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/poetry/bin/pip install --upgrade "pip==${PIP_VERSION}"

ARG POETRY_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/poetry/bin/pip install "poetry==${POETRY_VERSION}" && \
    /opt/poetry/bin/poetry config virtualenvs.options.no-pip true && \
    /opt/poetry/bin/poetry config virtualenvs.options.no-setuptools true

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN /opt/poetry/bin/poetry export -f requirements.txt --output /tmp/requirements.txt


# Switch back to Alpine once this is resolved:
# https://github.com/firebase/firebase-tools/issues/5256#issuecomment-1383228506
# Alternatively, switch back to slim once this is resolved:
# https://github.com/TheKevJames/tools/issues/675
FROM google/cloud-sdk:465.0.0

ARG NETCATOPENBSD_VERSION
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        "netcat-openbsd=${NETCATOPENBSD_VERSION}" && \
    gcloud config set disable_usage_reporting true

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade "pip==${PIP_VERSION}"

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r /tmp/requirements.txt

COPY --from=fetcher /tmp/wait-for /usr/bin
COPY --link pubsubc.py /usr/bin/pubsubc
COPY --link run.sh /run.sh

EXPOSE 8681 8682/udp

ENTRYPOINT ["/run.sh"]
