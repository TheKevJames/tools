defmodule Poe.Api.Wiki do
  require Logger
  alias Poe.Cache

  # https://pathofexile.gamepedia.com/Special:CargoTables
  @api "https://pathofexile.gamepedia.com/api.php"

  # curl "https://pathofexile.gamepedia.com/api.php?action=cargoquery&tables=mods,spawn_weights&join_on=mods._pageID=spawn_weights._pageID&fields=mods.stat_text_raw,mods.tier_text,spawn_weights.weight&where=mods.domain=11%20AND%20spawn_weights.weight%3E0&limit=50&format=json"
  defp do_query(filter) do
    api =
      @api
      |> URI.parse()
      |> Map.put(
        :query,
        URI.encode_query(
          action: "cargoquery",
          fields: "mods.stat_text_raw,spawn_weights.weight",
          format: "json",
          join_on: "mods._pageID=spawn_weights._pageID",
          tables: "mods,spawn_weights",
          where: "#{filter} AND spawn_weights.weight>0"
        )
      )
      |> URI.to_string()

    case HTTPoison.get(api) do
      {:ok, %{status_code: 200, body: body}} ->
        case Jason.decode!(body) do
          %{"error" => %{"info" => err}} ->
            raise "wiki API returned error: #{err}"

          data ->
            Map.get(data, "cargoquery")
        end

      {:error, _} ->
        raise "unknown error hitting wiki API"
    end
  end

  defp do_map_mods(tag, generation) do
    filter =
      [
        "mods.domain=5",
        "mods.generation_type=#{generation}",
        "mods.name!=\"\"",
        "spawn_weights.tag=\"#{tag}\""
      ]
      |> Enum.join(" AND ")

    do_query(filter)
  end

  def map_mods(tag, generation) do
    key = {__MODULE__, :mapMods, tag, generation}

    case Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = do_map_mods(tag, generation)
        Cache.put(key, value)
        value
    end
  end

  def do_sextant_mods() do
    filter = ["mods.domain=11"] |> Enum.join(" AND ")
    do_query(filter)
  end

  def sextant_mods() do
    key = {__MODULE__, :sextantMods}

    case Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = do_sextant_mods()
        Cache.put(key, value)
        value
    end
  end
end
