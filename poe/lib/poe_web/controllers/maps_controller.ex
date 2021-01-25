defmodule PoeWeb.MapsController do
  require Logger
  use PoeWeb, :controller
  alias Poe.Maps

  def rows() do
    for tier <- 1..16 do
      returns = for {key, value} <- Maps.crafting_return(tier), into: %{} do
        color = case value do
          x when x < 0 -> "bg-red"
          x when x < 0.2 -> "bg-yellow"
          _ -> "bg-green"
        end
        {key, %{color: color, value: Float.round(value, 2)}}
      end
      Map.put(returns, :name, "T#{tier}")
    end
  end

  def index(conn, _params) do
    render(conn, "index.html", rows: rows())
  end
end
