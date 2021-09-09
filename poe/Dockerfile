FROM elixir:1.12.3-alpine AS build

RUN apk add --no-cache build-base git npm python2

WORKDIR /app
RUN mix local.hex --force && \
    mix local.rebar --force

ENV MIX_ENV=prod

COPY mix.exs mix.lock ./
COPY config config
RUN mix do deps.get, deps.compile

COPY assets/package.json assets/package-lock.json ./assets/
RUN npm --prefix ./assets ci --progress=false --no-audit --loglevel=error

COPY priv priv
COPY assets assets
RUN npm run --prefix ./assets deploy && \
    mix phx.digest

COPY lib lib
RUN mix do compile, release


FROM alpine:3.14 AS app

RUN apk add --no-cache ncurses-libs openssl

ENV HOME=/app

WORKDIR /app
COPY --from=build /app/_build/prod/rel/poe ./

CMD ["bin/poe", "start"]
