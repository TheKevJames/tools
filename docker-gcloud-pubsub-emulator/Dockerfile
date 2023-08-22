# syntax=docker/dockerfile:1.3
FROM curlimages/curl:latest as fetcher

ARG WAITFOR_VERSION=2.2.4
RUN curl -vsSLo /tmp/wait-for "https://github.com/eficode/wait-for/releases/download/v${WAITFOR_VERSION}/wait-for"
RUN chmod +x /tmp/wait-for


# N.B. match to the python3 version in the gcloud image
FROM python:3.9.2 AS builder

RUN python3 -m venv /opt/poetry
ARG PIP_VERSION=23.0.1
RUN /opt/poetry/bin/pip install --upgrade "pip==${PIP_VERSION}"
ARG POETRY_VERSION=1.4.0
RUN /opt/poetry/bin/pip install "poetry==${POETRY_VERSION}"
RUN /opt/poetry/bin/poetry config virtualenvs.options.no-pip true
RUN /opt/poetry/bin/poetry config virtualenvs.options.no-setuptools true

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN /opt/poetry/bin/poetry export -f requirements.txt --output /tmp/requirements.txt


# Switch back to Alpine once this is resolved:
# https://github.com/firebase/firebase-tools/issues/5256#issuecomment-1383228506
FROM google/cloud-sdk:444.0.0

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
ARG NETCAT_VERSION=1.217-3
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        "netcat-openbsd=${NETCAT_VERSION}" && \
    gcloud config set disable_usage_reporting true

ARG PIP_VERSION=23.0.1
RUN python3 -m pip install --upgrade "pip==${PIP_VERSION}"

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r /tmp/requirements.txt

COPY --from=fetcher /tmp/wait-for /usr/bin
COPY pubsubc.py /usr/bin/pubsubc
COPY run.sh /run.sh

EXPOSE 8681 8682/udp

ENTRYPOINT ["/run.sh"]
