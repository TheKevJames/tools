# syntax=docker/dockerfile:1

# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=23.3.2
# renovate: datasource=pypi depName=fava
ARG FAVA_VERSION=1.27.1


FROM python:3.12.1-alpine

RUN --mount=type=cache,target=/var/cache/apk \
    apk add -U \
        gcc \
        musl-dev

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade "pip==${PIP_VERSION}"

ARG FAVA_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install "fava==${FAVA_VERSION}"

ENV FAVA_HOST=0.0.0.0
ENTRYPOINT ["fava"]
