import Config

secret_key_base =
  System.get_env("SECRET_KEY_BASE") ||
    raise """
    environment variable SECRET_KEY_BASE is missing.
    You can generate one by calling: mix phx.gen.secret
    """

config :poe, PoeWeb.Endpoint,
  http: [
    port: String.to_integer(System.get_env("PORT") || "80"),
    transport_options: [socket_opts: [:inet6]]
  ],
  # TODO: fallback to no HTTP when values are unset
  https: [
    port: String.to_integer(System.get_env("PORTS") || "443"),
    cipher_suite: :strong,
    otp_app: :poe,
    keyfile: System.get_env("SSL_KEY"),
    certfile: System.get_env("SSL_CERT")
  ],
  secret_key_base: secret_key_base

config :poe, PoeWeb.Endpoint, server: true
