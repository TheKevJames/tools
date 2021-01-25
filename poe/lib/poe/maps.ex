defmodule Poe.Maps.Mod do
  require Logger

  defstruct [:name, em: 0, iiq: 0, iir: 0, ps: 0, weight: 0]

  def bonus(mod) do
    # TODO: include iir
    (1 + mod.iiq / 100.0) * (1 + mod.ps / 100.0) * (1 + mod.em / 50.0)
  end

  # TODO: calculate em from flat added pack count
  # https://i.imgur.com/MZ69Pw8.png
  # bountiful traps -> 18 packs
  # sextant mods

  def from_map(%{"title" => %{"name" => name, "stat text raw" => raw_stats, "weight" => weight}}) do
    stats =
      Enum.reduce(String.split(raw_stats, "&lt;br&gt;"), %{}, fn stat, acc ->
        cond do
          matches = Regex.run(~r/(.*)%.*increased quantity of items/i, stat) ->
            Map.put(acc, :iiq, String.to_integer(Enum.at(matches, 1)))

          matches = Regex.run(~r/(.*)%.*increased rarity of items/i, stat) ->
            Map.put(acc, :iir, String.to_integer(Enum.at(matches, 1)))

          matches = Regex.run(~r/\+(.*)%.*monster pack size/i, stat) ->
            Map.put(acc, :ps, String.to_integer(Enum.at(matches, 1)))

          matches = Regex.run(~r/(.*)%.*increased magic pack size/i, stat) ->
            Map.put(acc, :ps, String.to_integer(Enum.at(matches, 1)))

          true ->
            # TODO: any others to parse?
            # Logger.debug("ignoring mod stat: #{stat}")
            acc
        end
      end)

    %Poe.Maps.Mod{
      name: name,
      em: Map.get(stats, :em, 0),
      iiq: Map.get(stats, :iiq, 0),
      iir: Map.get(stats, :iiq, 0),
      ps: Map.get(stats, :ps, 0),
      weight: String.to_integer(weight)
    }
  end
end

defmodule Poe.Maps do
  require Logger
  alias Poe.Market
  alias Poe.Maps.Mod

  def affix(tier) do
    tag =
      case tier do
        n when n > 10 ->
          "top_tier_map"

        n when n > 5 ->
          "mid_tier_map"

        n when n > 0 ->
          "low_tier_map"

        _ ->
          Logger.error("invalid map tier #{tier}")
          "low_tier_map"
      end

    prefixes = mods(5, "default", 1) ++ mods(5, tag, 1)

    prefix =
      Enum.sum(Enum.map(prefixes, &(&1.weight * Mod.bonus(&1)))) /
        Enum.sum(Enum.map(prefixes, & &1.weight))

    suffixes = mods(5, "default", 2) ++ mods(5, tag, 2)

    suffix =
      Enum.sum(Enum.map(suffixes, &(&1.weight * Mod.bonus(&1)))) /
        Enum.sum(Enum.map(suffixes, & &1.weight))

    (prefix + suffix) / 2.0
  end

  def fetch_mods(domain, tag, generation) do
    api = "https://pathofexile.gamepedia.com/api.php"
    # TODO: ew
    filter =
      case domain do
        5 ->
          "mods.domain=5 AND mods.generation_type=#{generation} AND mods.name!=\"\" AND spawn_weights.tag=\"#{
            tag
          }\""

        11 ->
          "mods.domain=11"

        _ ->
          Logger.error("searching for invalid mod domain #{domain}")
          ""
      end

    url =
      api
      |> URI.parse()
      |> Map.put(
        :query,
        URI.encode_query(
          action: "cargoquery",
          fields: "mods.name,mods.stat_text_raw,spawn_weights.weight",
          format: "json",
          join_on: "mods._pageID=spawn_weights._pageID",
          tables: "mods,spawn_weights",
          where: "#{filter} AND spawn_weights.weight>0"
        )
      )
      |> URI.to_string()

    case HTTPoison.get(url) do
      {:ok, %{status_code: 200, body: body}} ->
        case Jason.decode!(body) do
          %{"error" => %{"info" => info}} ->
            Logger.error("cargoquery API returned error: #{info}")

          data ->
            Enum.map(Map.get(data, "cargoquery"), &Mod.from_map/1)
        end

      {:error, _} ->
        Logger.error("unknown error hitting cargoquery API")
    end
  end

  def mods(domain, tag, generation) do
    key = {__MODULE__, domain, tag, generation}

    case Poe.Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = fetch_mods(domain, tag, generation)
        Poe.Cache.put(key, value)
        value
    end
  end

  # TODO: get real numbers on this
  # current numbers from https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/
  def base(tier) do
    # https://i.imgur.com/AsOZpGt.png
    """
    Enum.at(
      [
        0.63,
        0.41,
        0.45,
        0.58,
        0.61,
        0.87,
        1.03,
        1.53,
        1.91,
        1.83,
        3.3,
        3.5,
        5.7,
        8.5,
        12.6,
        13.5
      ],
      tier - 1
    )
    """
    # https://docs.google.com/spreadsheets/d/1Mdl01Fc4DycxeXrKxj_R0rIybmQVowEc0TKNtLzpLGM/edit#gid=1120006489
    # wolfram alpha: fit [{1, 0.5}, {3, 1}, {6, 3}, {11, 5.096}, {12, 4.697}, {13, 6.189}, {14, 7.392}, {15, 13.443}, {16, 14.487}]
    # quartic model seemed visually reasonable. cubic and exponential both looked valid
    # hard data only exists for T11+ in v3.5.0
    # TODO: add {9, 3.9} from https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/ec88th2?utm_source=share&utm_medium=web2x&context=3
    0.00139194 * :math.pow(tier, 4) - 0.0340657 * :math.pow(tier, 3) + 0.262759 * :math.pow(tier, 2) - 0.250333 * tier + 0.426206
  end

  def craft_alch(tier) do
    base(tier) * :math.pow(affix(tier), 5) - base(tier) - Market.cost(:alch)
  end

  def craft_chisel(tier) do
    base(tier) * Mod.bonus(%Mod{iiq: 20}) - base(tier) - Market.cost(:chis) * 4
  end

  # TODO: find the math behind this one
  def craft_emprop(tier) do
    base(tier) * 1.16 - base(tier) - Market.cost(:empr)
  end

  # TODO: calculate with multiple fragments
  def craft_fragment(tier) do
    base(tier) * Mod.bonus(%Mod{iiq: 5}) - base(tier) - Market.cost(:frag)
  end

  # TODO: pulled from https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/
  # This is definitely out-of-date data, this spreadsheet might be more accurate:
  # https://docs.google.com/spreadsheets/d/1sSPczBrOK-xQSXgvgZ55Zq8uS9CVDsXFrpzgD-m9cSQ/edit#gid=1731351453
  def craft_sextant(kind, tier) do
    base(tier) * 1.13 - base(tier) - Market.cost(kind)
  end

  def craft_tempest(tier) do
    base(tier) * Mod.bonus(%Mod{iiq: 30, iir: 30}) - base(tier) - Market.cost(:temp)
  end

  # TODO: old data; need to calculate 18 packs -> Mod.em to make this accurate
  def craft_traps(tier) do
    base(tier) * 1.33 - base(tier) - Market.cost(:trap)
  end

  def craft_vaal(tier) do
    effects = [
      # nada
      base(tier),
      base(tier),
      # reroll
      base(tier) * :math.pow(affix(tier), 5),
      # uptier and reroll
      # T16s can't uptier
      base(min(tier + 1, 16)) * :math.pow(affix(min(tier + 1, 16)), 5),
      # full reroll
      base(tier) * :math.pow(affix(tier), 8),
      base(tier) * :math.pow(affix(tier), 8),
      # unidentify
      base(tier) * Mod.bonus(%Mod{iiq: 30}),
      base(tier) * Mod.bonus(%Mod{iiq: 30})
    ]

    Enum.sum(effects) / length(effects) - base(tier) - Market.cost(:vaal)
  end

  # TODO: get all these, compare to default (eg. :iiq)
  def craft_zana(kind, tier) do
    effects = %{
      # TODO: 3 strongboxes
      amb: 1,
      # TODO: 3 exiles
      ana: 1,
      # TODO: chance of beyonds
      bey: 1,
      # TODO: 4 shrines
      dom: 1,
      iiq: Mod.bonus(%Mod{iiq: 8}),
      # TODO: 1 legion
      leg: 1,
      per: 3 * 30 * Market.cost(:pdus),
      # TODO: 3 warbands
      war: 1
    }

    {mult, cost} =
      case kind do
        :amb -> {Map.get(effects, kind), 3}
        :ana -> {Map.get(effects, kind), 2}
        :bey -> {Map.get(effects, kind), 5}
        :dom -> {Map.get(effects, kind), 4}
        :ffb -> {Enum.sum(Map.values(effects)) / map_size(effects), 3}
        :iiq -> {Map.get(effects, kind), 0}
        :leg -> {Map.get(effects, kind), 6}
        :per -> {Map.get(effects, kind), 4}
        :war -> {Map.get(effects, kind), 2}
      end

    base(tier) * mult - base(tier) - cost
  end

  # TODO: not quite right; bonuses are multiplicative
  def crafting_return(tier) do
    # TODO: scarabs, transmute, chance
    %{
      alch: craft_alch(tier),
      chis: craft_chisel(tier),
      empr: craft_emprop(tier),
      frag: craft_fragment(tier),
      sexa: craft_sextant(:sexa, tier),
      sexp: craft_sextant(:sexp, tier),
      sexs: craft_sextant(:sexs, tier),
      temp: craft_tempest(tier),
      trap: craft_traps(tier),
      vaal: craft_vaal(tier),
      zamb: craft_zana(:amb, tier),
      zana: craft_zana(:ana, tier),
      zbey: craft_zana(:bey, tier),
      zdom: craft_zana(:dom, tier),
      zffb: craft_zana(:ffb, tier),
      ziiq: craft_zana(:iiq, tier),
      zleg: craft_zana(:leg, tier),
      zper: craft_zana(:per, tier),
      zwar: craft_zana(:war, tier)
    }
  end
end
