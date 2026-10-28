# syntax=docker/dockerfile:1

# renovate: datasource=pypi depName=beancount
ARG BEANCOUNT_VERSION=3.2.3
# renovate: datasource=pypi depName=fava
ARG FAVA_VERSION=1.30.16


FROM python:3.15.2-alpine AS builder

# TODO: pin versions and let renovate update them
RUN --mount=type=cache,target=/var/cache/apk \
    apk --update add \
        build-base \
        flex \
        python3-dev

ARG BEANCOUNT_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip wheel --no-deps --wheel-dir=/tmp \
        "beancount==${BEANCOUNT_VERSION}"


FROM python:3.15.2-alpine

ARG BEANCOUNT_VERSION
COPY --from=builder "/tmp/beancount-${BEANCOUNT_VERSION}-cp315-cp315-linux_aarch64.whl" "/tmp/beancount-${BEANCOUNT_VERSION}-cp315-cp315-linux_aarch64.whl"
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install \
        "/tmp/beancount-${BEANCOUNT_VERSION}-cp315-cp315-linux_aarch64.whl"

ARG FAVA_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install \
        "fava==${FAVA_VERSION}"

ENV FAVA_HOST=0.0.0.0
ENTRYPOINT ["fava"]
