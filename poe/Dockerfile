FROM elixir:1.13.1-alpine AS build

RUN apk add --no-cache build-base git python2

WORKDIR /app
RUN mix local.hex --force && \
    mix local.rebar --force

ENV MIX_ENV=prod

COPY mix.exs mix.lock ./
COPY config config
RUN mix do deps.get, deps.compile

COPY priv priv
COPY assets assets
RUN mix esbuild default --minify && \
    mix phx.digest

COPY lib lib
RUN mix do compile, release


FROM alpine:3.15 AS app

RUN apk add --no-cache ncurses-libs openssl

ENV HOME=/app

WORKDIR /app
COPY --from=build /app/_build/prod/rel/poe ./

CMD ["bin/poe", "start"]
