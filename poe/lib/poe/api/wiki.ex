defmodule Poe.Api.Wiki do
  require Logger
  alias Poe.Cache

  # https://pathofexile.gamepedia.com/Special:CargoTables
  @api "https://pathofexile.gamepedia.com/api.php"
  # TODO: Ritual data not yet loaded into the wiki
  @league "Heist"

  # curl "https://pathofexile.gamepedia.com/api.php?action=cargoquery&tables=mods,spawn_weights&join_on=mods._pageID=spawn_weights._pageID&fields=mods.stat_text_raw,mods.tier_text,spawn_weights.weight&where=mods.domain=11%20AND%20spawn_weights.weight%3E0&limit=50&format=json"
  defp do_query(query) do
    api =
      @api
      |> URI.parse()
      |> Map.put(:query, query)
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

  defp do_maps() do
    do_query(
      URI.encode_query(
        action: "cargoquery",
        fields: "maps.tier,items.name",
        format: "json",
        join_on: "maps._pageName=items._pageName",
        limit: 500,
        tables: "maps,items",
        where: "items.class=\"Maps\" AND maps.series=\"#{@league}\""
      )
    )
  end

  def maps() do
    key = {__MODULE__, :maps}

    case Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = do_maps()
        Cache.put(key, value)
        value
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

    do_query(
      URI.encode_query(
        action: "cargoquery",
        fields: "mods.stat_text_raw,spawn_weights.weight",
        format: "json",
        join_on: "mods._pageID=spawn_weights._pageID",
        limit: 100,
        tables: "mods,spawn_weights",
        where: "#{filter} AND spawn_weights.weight>0"
      )
    )
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

  def do_pantheon_souls() do
    do_query(
      URI.encode_query(
        action: "cargoquery",
        fields: "id,stat_text,target_area_id",
        format: "json",
        limit: 50,
        tables: "pantheon_souls"
      )
    )
  end

  def pantheon_souls() do
    key = {__MODULE__, :pantheonSouls}

    case Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = do_pantheon_souls()
        Cache.put(key, value)
        value
    end
  end

  def do_sextant_mods() do
    do_query(
      URI.encode_query(
        action: "cargoquery",
        fields: "mods.stat_text_raw,spawn_weights.weight",
        format: "json",
        join_on: "mods._pageID=spawn_weights._pageID",
        limit: 500,
        tables: "mods,spawn_weights",
        where: "mods.domain=11 AND spawn_weights.weight>0"
      )
    )
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
