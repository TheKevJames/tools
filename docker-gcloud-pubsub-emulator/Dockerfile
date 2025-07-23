# syntax=docker/dockerfile:1

# renovate: datasource=repology depName=debian_12/netcat-openbsd versioning=loose
ARG NETCATOPENBSD_VERSION=1.219-1
# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=25.1.1
# renovate: datasource=pypi depName=poetry
ARG POETRY_VERSION=2.1.3
# renovate: datasource=pypi depName=poetry-plugin-export
ARG POETRYPLUGINEXPORT_VERSION=1.9.0
# renovate: datasource=repology depName=debian_12/python3-pip versioning=loose
ARG PYTHON3PIP_VERSION=25.1.1+dfsg-1
# renovate: datasource=repology depName=debian_12/python3-venv versioning=loose
ARG PYTHON3VENV_VERSION=3.11.2-1
# renovate: datasource=github-releases depName=eficode/wait-for
ARG WAITFOR_VERSION=2.2.4


FROM curlimages/curl:8.15.0 AS fetcher

ARG WAITFOR_VERSION
RUN curl -vsSLo /tmp/wait-for "https://github.com/eficode/wait-for/releases/download/v${WAITFOR_VERSION}/wait-for" && \
    chmod +x /tmp/wait-for


FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:531.0.0-emulators AS base

ARG TARGETPLATFORM
ARG NETCATOPENBSD_VERSION
ARG PYTHON3PIP_VERSION

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt,id=apt-cache-$TARGETPLATFORM \
    --mount=type=cache,sharing=locked,target=/var/lib/apt,id=apt-lib-$TARGETPLATFORM \
    apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        "netcat-openbsd=${NETCATOPENBSD_VERSION}" \
        "python3-pip=${PYTHON3PIP_VERSION}" && \
    gcloud config set disable_usage_reporting true


FROM base AS builder

ARG TARGETPLATFORM
ARG PYTHON3VENV_VERSION

RUN --mount=type=cache,sharing=locked,target=/var/cache/apt,id=apt-cache-$TARGETPLATFORM \
    --mount=type=cache,sharing=locked,target=/var/lib/apt,id=apt-lib-$TARGETPLATFORM \
    apt-get install -qy --no-install-recommends \
        "python3-venv=${PYTHON3VENV_VERSION}" && \
    python3 -m venv /opt/poetry

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


FROM base

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade "pip==${PIP_VERSION}" --break-system-packages

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install -r /tmp/requirements.txt --break-system-packages

COPY --from=fetcher /tmp/wait-for /usr/bin
COPY --link pubsubc.py /usr/bin/pubsubc
COPY --link run /usr/bin/run

EXPOSE 8681 8682/udp

ENTRYPOINT ["/usr/bin/run"]
