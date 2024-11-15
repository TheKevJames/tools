# syntax=docker/dockerfile:1

# https://pkgs.alpinelinux.org/packages?name=&branch=v3.20&repo=&arch=&maintainer=
# renovate: datasource=repology depName=alpine_3_20/gcc versioning=loose
ARG GCC_VERSION=13.2.1_git20240309-r0
# renovate: datasource=repology depName=alpine_3_20/musl-dev versioning=loose
ARG MUSLDEV_VERSION=1.2.5-r0
# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=24.3.1
# renovate: datasource=pypi depName=fava
ARG FAVA_VERSION=1.27.3


FROM python:3.13.0-alpine

ARG GCC_VERSION
ARG MUSLDEV_VERSION
RUN --mount=type=cache,target=/var/cache/apk \
    apk add -U \
        "gcc=${GCC_VERSION}" \
        "musl-dev=${MUSLDEV_VERSION}"

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade "pip==${PIP_VERSION}"

ARG FAVA_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install "fava==${FAVA_VERSION}"

ENV FAVA_HOST=0.0.0.0
ENTRYPOINT ["fava"]
