use Mix.Config

# Configures the endpoint
config :poe, PoeWeb.Endpoint,
  url: [host: "localhost"],
  secret_key_base: "5B2VcxEyeTuQWafvlIVGxwaAKGRYffxw/UO2IqoQW/DKP1fPgR1Rsbw4uGbSSY+A",
  render_errors: [view: PoeWeb.ErrorView, accepts: ~w(html json), layout: false],
  pubsub_server: Poe.PubSub,
  live_view: [signing_salt: "A16Zk+Vi"]

# Configures Elixir's Logger
config :logger, :console,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

import_config "#{Mix.env()}.exs"
