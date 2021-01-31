use Mix.Config

config :poe, PoeWeb.Endpoint,
  http: [port: 80],
  url: [host: "poe.thekev.in", port: 80],
  cache_static_manifest: "priv/static/cache_manifest.json"

config :logger, level: :info
