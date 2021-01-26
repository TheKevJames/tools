defmodule PoeWeb.MapsController do
  require Logger
  use PoeWeb, :controller
  alias Poe.Maps

  def cols() do
    [
      {:base, "Base Value"},
      {:alch, "+Alch"},
      {:chis, "+Chisel"},
      {:vaal, "+Vaal"},
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
      {:zleg, "Zana (Legion)"},
      # {:zper, "Zana (Perandus)"},
      # {:zwar, "Zana (Warbands)"},
      # {:zffb, "Zana (Random)"},
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
    render(conn, "index.html", cols: cols(), rows: rows())
  end
end
