defmodule PoeWeb.MapsController do
  require Logger
  use PoeWeb, :controller
  alias Poe.Api.Ninja
  alias Poe.Maps

  def cols() do
    [
      {:base, "Base"},
      {:alch, "Alch"},
      {:chis, "Chisel"},
      {:vaal, "Vaal"},
      {:frag, "Fragment"},
      {:temp, "Prophecy (Tempest)"},
      {:empr, "Prophecy (Extra Monsters)"},
      {:trap, "Prophecy (Bountiful Traps)"},
      {:sexs, "Simple Sextant"},
      {:sexp, "Prime Sextant"},
      {:sexa, "Awakened Sextant"},
      # {:ziiq, "Zana (No Mod)"},
      {:zamb, "Zana (Ambush)"},
      # {:zana, "Zana (Anarchy)"},
      # {:zbey, "Zana (Beyond)"},
      # {:zdom, "Zana (Domination)"},
      {:zleg, "Zana (Legion)"}
      # {:zper, "Zana (Perandus)"},
      # {:zwar, "Zana (Warbands)"},
      # {:zffb, "Zana (Random)"},
    ]
  end

  def prices() do
    [
      {:alch, Float.round(Ninja.currency(:alch), 3)},
      {:chis, Float.round(Ninja.currency(:chis), 3)},
      {:vaal, Float.round(Ninja.currency(:vaal), 3)},
      {:frag, Float.round(Ninja.fragment(:sacr), 3)},
      {:temp, Float.round(Ninja.prophecy(:temp), 3)},
      {:trap, Float.round(Ninja.prophecy(:trap), 3)},
      {:empr, Float.round(Ninja.prophecy(:extr), 3)},
      {:sexs, Float.round(Ninja.currency(:sexs), 3)},
      {:sexp, Float.round(Ninja.currency(:sexp), 3)},
      {:sexa, Float.round(Ninja.currency(:sexa), 3)}
    ]
  end

  def rows() do
    for tier <- 1..16 do
      returns =
        for {key, value} <- Maps.crafting_return(tier), into: %{} do
          color =
            case value do
              x when x < 0 -> "bg-red"
              x when x < 0.5 -> "bg-yellow"
              _ -> "bg-green"
            end

          {key, %{color: color, value: Float.round(value, 2)}}
        end

      Map.put(returns, :name, "T#{tier}")
    end
  end

  def index(conn, _params) do
    render(conn, "index.html", cols: cols(), prices: prices(), rows: rows())
  end
end
