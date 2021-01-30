use Mix.Config

config :poe, PoeWeb.Endpoint,
  http: [port: 4002],
  server: false

config :logger, level: :warn
