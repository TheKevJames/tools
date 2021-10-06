defmodule Poe.Api.Ninja do
  require Logger
  alias Poe.Cache

  @api "https://poe.ninja/api/data"
  @league "Ritual"

  # curl "https://poe.ninja/api/data/CurrencyOverview?league=Ritual&type=Currency&language=en" | jq '.lines[]|select(.currencyTypeName=="Scroll of Wisdom").receive.value'
  defp do_query(route, kind) do
    api =
      "#{@api}/#{route}"
      |> URI.parse()
      |> Map.put(
        :query,
        URI.encode_query(
          league: @league,
          type: kind,
          language: "en"
        )
      )
      |> URI.to_string()

    case HTTPoison.get(api) do
      {:ok, %{status_code: 200, body: ""}} ->
        raise "empty poe.ninja response"
      {:ok, %{status_code: 200, body: body}} ->
        case Jason.decode!(body) do
          %{"lines" => data} ->
            data

          err ->
            raise "unexpected poe.ninja response: #{inspect(err)}"
        end

      {:error, _} ->
        raise "unknown error hitting poe.ninja API"
    end
  end

  defp do_currency() do
    data = do_query("CurrencyOverview", "Currency")

    %{"receive" => %{"value" => alch}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Orb of Alchemy" end)

    %{"receive" => %{"value" => chisel}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Cartographer's Chisel" end)

    %{"receive" => %{"value" => vaal}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Vaal Orb" end)

    %{"receive" => %{"value" => sexa}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Awakened Sextant" end)

    %{"receive" => %{"value" => sexs}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Simple Sextant" end)

    %{"receive" => %{"value" => sexp}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Prime Sextant" end)

    %{
      alch: alch,
      chis: chisel,
      sexa: sexa,
      sexs: sexs,
      sexp: sexp,
      vaal: vaal
    }
  end

  def currency(kind) do
    key = {__MODULE__, :currency}

    case Cache.get(key) do
      {:hit, value} ->
        Map.get(value, kind)

      {:miss} ->
        value = do_currency()
        Cache.put(key, value)
        Map.get(value, kind)
    end
  end

  defp do_fragment() do
    data = do_query("CurrencyOverview", "Fragment")

    %{"receive" => %{"value" => sacrificeDawn}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Sacrifice at Dawn" end)

    %{"receive" => %{"value" => sacrificeDusk}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Sacrifice at Dusk" end)

    %{"receive" => %{"value" => sacrificeMidnight}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Sacrifice at Midnight" end)

    %{"receive" => %{"value" => sacrificeNoon}} =
      Enum.find(data, fn x -> x["currencyTypeName"] == "Sacrifice at Noon" end)

    %{sacr: Enum.min([sacrificeDawn, sacrificeDusk, sacrificeMidnight, sacrificeNoon])}
  end

  def fragment(kind) do
    key = {__MODULE__, :fragment}

    case Cache.get(key) do
      {:hit, value} ->
        Map.get(value, kind)

      {:miss} ->
        value = do_fragment()
        Cache.put(key, value)
        Map.get(value, kind)
    end
  end

  defp do_prophecy() do
    data = do_query("ItemOverview", "Prophecy")

    %{"chaosValue" => bountifulTraps} =
      Enum.find(data, fn x -> x["name"] == "Bountiful Traps" end)

    %{"chaosValue" => crushingSquall} =
      Enum.find(data, fn x -> x["name"] == "Crushing Squall" end)

    %{"chaosValue" => fireSky} = Enum.find(data, fn x -> x["name"] == "Fire from the Sky" end)

    %{"chaosValue" => frogs} = Enum.find(data, fn x -> x["name"] == "Plague of Frogs" end)

    %{"chaosValue" => iceAbove} = Enum.find(data, fn x -> x["name"] == "Ice from Above" end)

    %{"chaosValue" => lightningFalls} =
      Enum.find(data, fn x -> x["name"] == "Lightning Falls" end)

    %{"chaosValue" => rats} = Enum.find(data, fn x -> x["name"] == "Plague of Rats" end)

    %{"chaosValue" => undeadStorm} = Enum.find(data, fn x -> x["name"] == "The Undead Storm" end)

    %{"chaosValue" => vaalWinds} = Enum.find(data, fn x -> x["name"] == "Vaal Winds" end)

    %{"chaosValue" => worms} = Enum.find(data, fn x -> x["name"] == "Soil, Worms and Blood" end)

    %{
      extr: Enum.min([frogs, rats, worms]),
      temp: Enum.min([crushingSquall, fireSky, iceAbove, lightningFalls, undeadStorm, vaalWinds]),
      trap: bountifulTraps
    }
  end

  def prophecy(kind) do
    key = {__MODULE__, :prophecy}

    case Cache.get(key) do
      {:hit, value} ->
        Map.get(value, kind)

      {:miss} ->
        value = do_prophecy()
        Cache.put(key, value)
        Map.get(value, kind)
    end
  end
end
