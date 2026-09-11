# syntax=docker/dockerfile:1

FROM python:3.13.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-emit-project --no-dev -o /tmp/requirements.txt


FROM python:3.13.15-slim

COPY --from=builder /tmp/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --no-cache-dir -r /tmp/requirements.txt --break-system-packages

COPY ./atc1441_exporter /app

ENTRYPOINT ["python3", "-m", "app.main"]
