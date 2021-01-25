defmodule Poe.Application do
  @moduledoc false

  use Application

  def start(_type, _args) do
    children = [
      PoeWeb.Telemetry,
      {Phoenix.PubSub, name: Poe.PubSub},
      PoeWeb.Endpoint
      # {Poe.Worker, arg}
    ]

    opts = [strategy: :one_for_one, name: Poe.Supervisor]
    Supervisor.start_link(children, opts)
  end

  def config_change(changed, _new, removed) do
    PoeWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
