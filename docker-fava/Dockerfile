# syntax=docker/dockerfile:1.6
FROM python:3.12.1-alpine

ARG PIP_VERSION=23.0.1
RUN python3 -m pip install --upgrade "pip==${PIP_VERSION}"

ARG FAVA_VERSION=1.27.1
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install "fava==${FAVA_VERSION}"

ENTRYPOINT ["fava"]
