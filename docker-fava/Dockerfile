# syntax=docker/dockerfile:1

# renovate: datasource=pypi depName=pip
ARG PIP_VERSION=25.1.1
# renovate: datasource=pypi depName=fava
ARG FAVA_VERSION=1.30.7


# TODO: get alpine wheels for beancount
FROM python:3.13.6-slim-bullseye

ARG PIP_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade "pip==${PIP_VERSION}"

ARG FAVA_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install "fava==${FAVA_VERSION}"

ENV FAVA_HOST=0.0.0.0
ENTRYPOINT ["fava"]
