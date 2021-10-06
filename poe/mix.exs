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
      {:esbuild, "== 0.3.1", runtime: Mix.env() == :dev},
      {:gettext, "0.18.2"},
      {:httpoison, "1.8.0"},
      {:jason, "1.2.2"},
      {:phoenix, "== 1.6.0"},
      {:phoenix_html, "== 3.0.4"},
      {:phoenix_live_dashboard, "== 0.5.2"},
      {:phoenix_live_reload, "== 1.3.3", only: :dev},
      {:plug_cowboy, "== 2.5.2"},
      {:telemetry_metrics, "== 0.6.1"},
      {:telemetry_poller, "0.5.1"}
    ]
  end

  defp aliases, do: []
end
