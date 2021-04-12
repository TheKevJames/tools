defmodule Poe.MixProject do
  use Mix.Project

  def project do
    [
      app: :poe,
      version: "0.1.0",
      elixir: "~> 1.7",
      elixirc_paths: elixirc_paths(Mix.env()),
      compilers: [:phoenix, :gettext] ++ Mix.compilers(),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps()
    ]
  end

  def application do
    [
      mod: {Poe.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  defp deps do
    [
      {:gettext, "0.18.2"},
      {:httpoison, "1.8.0"},
      {:jason, "1.2.2"},
      {:phoenix, "1.5.7"},
      {:phoenix_html, "2.14.3"},
      {:phoenix_live_dashboard, "0.4.0"},
      {:phoenix_live_reload, "== 1.3.1", only: :dev},
      {:plug_cowboy, "2.4.1"},
      {:telemetry_metrics, "0.6.0"},
      {:telemetry_poller, "0.5.1"}
    ]
  end

  defp aliases do
    [
      setup: ["deps.get", "cmd npm install --prefix assets"]
    ]
  end
end
