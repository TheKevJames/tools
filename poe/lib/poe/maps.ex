defmodule Poe.Maps.Mod do
  require Logger

  defstruct em: 0, iiq: 0, iir: 0, ps: 0, weight: 0

  # Not much data on expected number and size of packs, but:
  #   https://i.imgur.com/MZ69Pw8.png shows pack size is about constant
  #   seems like most packs are ~10 on white maps
  #   players seem to agree on ~80:19:1 common:magic:rare
  @mobs 55
  @magic @mobs * 0.19

  def bonus(mod) do
    # TODO: IIR should have an effect somehow...
    (1 + mod.iiq / 100.0) * (1 + mod.ps / 100.0) * (1 + mod.em / @mobs)
  end

  def weighted(mod) do
    %Poe.Maps.Mod{
      em: mod.em * mod.weight,
      iiq: mod.iiq * mod.weight,
      iir: mod.iir * mod.weight,
      ps: mod.ps * mod.weight
    }
  end

  def div(mod, factor) do
    %Poe.Maps.Mod{
      em: mod.em / factor,
      iiq: mod.iiq / factor,
      iir: mod.iir / factor,
      ps: mod.ps / factor
    }
  end

  def add(mod, rhs) do
    %Poe.Maps.Mod{
      em: mod.em + rhs.em,
      iiq: mod.iiq + rhs.iiq,
      iir: mod.iir + rhs.iir,
      ps: mod.ps + rhs.ps
    }
  end

  def pow(mod, factor) do
    power = fn n, x -> (:math.pow(1 + n / 100.0, x) - 1) * 100 end

    %Poe.Maps.Mod{
      em: power.(mod.em, factor),
      iiq: power.(mod.iiq, factor),
      iir: power.(mod.iir, factor),
      ps: power.(mod.ps, factor)
    }
  end

  def from_map(%{"title" => %{"stat text raw" => raw_stats, "weight" => weight}}) do
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

          matches = Regex.run(~r/\((.*)-(.*)\)%.*more magic monsters/i, stat) ->
            avg_more =
              (String.to_integer(Enum.at(matches, 1)) + String.to_integer(Enum.at(matches, 2))) /
                2

            Map.put(acc, :em, @magic * avg_more)

          matches = Regex.run(~r/(.*)%.*increased pack size in unidentified maps/i, stat) ->
            # TODO: only for unidentified maps... but then, probably reasonable to assume folks
            # only run unidentified when they have this sextant mod
            Map.put(acc, :ps, String.to_integer(Enum.at(matches, 1)))

          matches = Regex.run(~r/areas contain (.*) additional packs of monsters/i, stat) ->
            Map.put(acc, :em, String.to_integer(Enum.at(matches, 1)))

          matches =
              Regex.run(~r/area contains (.*) additional packs of corrupted vaal monsters/i, stat) ->
            # TODO: do corrupted monsters drop better loot?
            Map.put(acc, :em, String.to_integer(Enum.at(matches, 1)))

          _matches =
              Regex.run(~r/areas contain (.*) additional clusters of mysterious barrels/i, stat) ->
            # TODO: looks like this might be a roll beteen :em and :iiq ?
            acc

          # TODO: various sextant mods:
          # Areas contain 2 additional Essences
          # Areas contain 2 additional Breaches
          # Areas contain an additional Abyss
          # Areas contain 2 additional Abysses
          # Areas are inhabited by an additional Invasion Boss
          # Area has 50% chance to contain Gifts

          true ->
            # TODO: any others to parse?
            # Logger.debug("ignoring mod stat: #{stat}")
            acc
        end
      end)

    %Poe.Maps.Mod{
      em: Map.get(stats, :em, 0),
      iiq: Map.get(stats, :iiq, 0),
      iir: Map.get(stats, :iiq, 0),
      ps: Map.get(stats, :ps, 0),
      weight: String.to_integer(weight)
    }
  end

  def from_maps(maps) do
    Enum.map(maps, &from_map/1)
  end
end

defmodule Poe.Maps do
  require Logger
  alias Poe.Api.Ninja
  alias Poe.Api.Wiki
  alias Poe.Cache
  alias Poe.Maps.Mod

  @enforce_keys [:tier, :value]
  defstruct [:tier, :value, cost: 0.0, mod: %Mod{}]

  def init(tier) do
    %Poe.Maps{tier: tier, value: base(tier)}
  end

  defp do_affix(%{sextant: _sextant}) do
    # TODO: figure out how to get only the mods for a specific tier of sextant
    # https://docs.google.com/spreadsheets/d/1sSPczBrOK-xQSXgvgZ55Zq8uS9CVDsXFrpzgD-m9cSQ/edit#gid=1731351453
    options = Wiki.sextant_mods() |> Mod.from_maps()
    weight = Enum.sum(Enum.map(options, & &1.weight))
    Mod.div(Enum.reduce(Enum.map(options, &Mod.weighted/1), %Mod{}, &Mod.add/2), weight)
  end

  defp do_affix(%{tier: tier}) do
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

    prefixes = Mod.from_maps(Wiki.map_mods("default", 1) ++ Wiki.map_mods(tag, 1))
    pweight = Enum.sum(Enum.map(prefixes, & &1.weight))

    prefix =
      Mod.div(Enum.reduce(Enum.map(prefixes, &Mod.weighted/1), %Mod{}, &Mod.add/2), pweight)

    suffixes = Mod.from_maps(Wiki.map_mods("default", 2) ++ Wiki.map_mods(tag, 2))
    pweight = Enum.sum(Enum.map(suffixes, & &1.weight))

    suffix =
      Mod.div(Enum.reduce(Enum.map(suffixes, &Mod.weighted/1), %Mod{}, &Mod.add/2), pweight)

    Mod.div(Mod.add(prefix, suffix), 2)
  end

  def affix(kind) do
    key = {__MODULE__, :affix, kind}

    case Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        value = do_affix(kind)
        Cache.put(key, value)
        value
    end
  end

  # TODO: get real numbers on this
  # current numbers from https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/
  def base(tier) do
    # https://i.imgur.com/AsOZpGt.png
    _ = """
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
    # hard data only exists for T11+ in v3.5.0
    # wolfram alpha: fit [{1, 0.3}, {3, 0.4}, {5, 0.6}, {6, 1.1}, {8, 2} {9, 3.9}, {11, 5.096}, {12, 4.697}, {13, 6.189}, {14, 7.392}, {15, 13.443}, {16, 14.487}]
    # exponential best fit:
    0.261393 * :math.exp(0.252491 * tier)
  end

  def craft(map, cost, mod) do
    %Poe.Maps{tier: map.tier, value: map.value, cost: map.cost + cost, mod: Mod.add(map.mod, mod)}
  end

  def return(map) do
    map.value * Mod.bonus(map.mod) - map.value - map.cost
  end

  def craft_alch(map) do
    craft(map, Ninja.currency(:alch), Mod.pow(affix(%{tier: map.tier}), 5))
  end

  def craft_chisel(map) do
    craft(map, Ninja.currency(:chis) * 4, %Mod{iiq: 20})
  end

  # TODO: find the math behind this one
  def craft_emprop(map) do
    craft(map, Ninja.prophecy(:extr), %Mod{ps: 16})
  end

  def craft_fragment(map) do
    craft(map, Ninja.fragment(:sacr), %Mod{iiq: 5})
  end

  def craft_sextant(map, kind) do
    craft(map, Ninja.currency(kind), affix(%{sextant: kind}))
  end

  def craft_tempest(map) do
    craft(map, Ninja.prophecy(:temp), %Mod{iiq: 30, iir: 30})
  end

  # TODO: shouldn't this also give a bit of bonus iiq?
  def craft_traps(map) do
    craft(map, Ninja.prophecy(:trap), %Mod{em: 18})
  end

  @doc """
  Implies craft_alch(map), since you would only ever vaal post-alch anyway and it keeps the math simpler.
  """
  def craft_vaal(map) do
    alched = craft_alch(map)

    results = [
      # nada
      alched.mod,
      alched.mod,
      # reroll
      Mod.add(map.mod, Mod.pow(affix(%{tier: map.tier}), 5)),
      # uptier and reroll (uptier logic in case below)
      # T16s can't uptier
      Mod.add(map.mod, Mod.pow(affix(%{tier: min(map.tier + 1, 16)}), 5)),
      # craft(init(tier + 1), map.cost, map.mod)
      # full reroll
      Mod.add(map.mod, Mod.pow(affix(%{tier: map.tier}), 8)),
      Mod.add(map.mod, Mod.pow(affix(%{tier: map.tier}), 8)),
      # unidentify
      Mod.add(alched.mod, %Mod{iiq: 30}),
      Mod.add(alched.mod, %Mod{iiq: 30})
    ]

    avg = Mod.div(Enum.reduce(results, %Mod{}, &Mod.add/2), length(results))

    tiered_map =
      case map.tier do
        n when n < 16 -> %{map | tier: map.tier + 1, value: base(map.tier + 1)}
        _ -> map
      end

    craft(tiered_map, Ninja.currency(:alch) + Ninja.currency(:vaal), avg)
  end

  def craft_zana(map, kind) do
    effects = %{
      # 3 strongboxes -> 9 mobs; TODO: probably some bonus iiq as well?
      amb: {0, %Mod{em: 9}},
      # 3 exiles -> 3 mobs?
      ana: {0, %Mod{em: 3}},
      # TODO: chance of beyonds, somehow exponential with :em?
      bey: {0, %Mod{}},
      # 4 shrines -> approx 6 packs?
      dom: {0, %Mod{em: 6}},
      iiq: {0, %Mod{iiq: 8}},
      # TODO: very inaccurate; based on 2019 post on farming tier 7s returning ~7.5c
      leg: {0, %Mod{em: 35}},
      # TODO: why are perandus coins not in poe.ninja?
      # 3 chests, ~30 coins per, value is 1/300c
      per: {3 * 30 * 1 / 300.0, %Mod{}},
      # 3 warbands -> 3 mobs?
      war: {0, %Mod{em: 3}}
    }

    ffb =
      {Enum.sum(Enum.map(Map.values(effects), fn {value, _} -> value end)) / map_size(effects),
       Enum.reduce(Enum.map(Map.values(effects), fn {_, mod} -> mod end), %Mod{}, &Mod.add/2)}

    {{value, mod}, cost} =
      case kind do
        :amb -> {Map.get(effects, kind), 3}
        :ana -> {Map.get(effects, kind), 2}
        :bey -> {Map.get(effects, kind), 5}
        :dom -> {Map.get(effects, kind), 4}
        :ffb -> {ffb, 3}
        :iiq -> {Map.get(effects, kind), 0}
        :leg -> {Map.get(effects, kind), 6}
        :per -> {Map.get(effects, kind), 4}
        :war -> {Map.get(effects, kind), 2}
      end

    craft(%{map | value: map.value + value}, cost, mod)
  end

  def crafting_return(tier) do
    # TODO: scarabs, transmute, chance
    map = init(tier)

    alch_net = map |> craft_alch |> return
    alch = alch_net - map.value

    chis_net =
      map |> craft_chisel |> (fn x -> (alch > 0 && x |> craft_alch) || x end).() |> return

    chis = chis_net - ((alch > 0 && alch_net) || map.value)

    vaal_net =
      map |> (fn x -> (chis > 0 && x |> craft_chisel) || x end).() |> craft_vaal |> return

    vaal = vaal_net - ((chis > 0 && chis_net) || alch_net)

    frag_net =
      map
      |> (fn x -> (chis > 0 && x |> craft_chisel) || x end).()
      |> (fn x -> (vaal > 0 && x |> craft_vaal) || ((alch > 0 && x |> craft_alch) || x) end).()
      |> craft_fragment
      |> return

    frag = frag_net - ((vaal > 0 && vaal_net) || ((chis > 0 && chis_net) || alch_net))

    crafted =
      map
      |> (fn x -> (chis > 0 && x |> craft_chisel) || x end).()
      |> (fn x -> (vaal > 0 && x |> craft_vaal) || ((alch > 0 && x |> craft_alch) || x) end).()
      |> (fn x -> (frag > 0 && x |> craft_fragment) || x end).()

    crafted_return = crafted |> return

    empr = (crafted |> craft_emprop |> return) - crafted_return
    temp = (crafted |> craft_tempest |> return) - crafted_return
    trap = (crafted |> craft_traps |> return) - crafted_return

    sexa = (crafted |> craft_sextant(:sexa) |> return) - crafted_return
    sexp = (crafted |> craft_sextant(:sexp) |> return) - crafted_return
    sexs = (crafted |> craft_sextant(:sexs) |> return) - crafted_return

    ziiq = (crafted |> craft_zana(:iiq) |> return) - crafted_return
    zamb = (crafted |> craft_zana(:amb) |> return) - crafted_return
    zana = (crafted |> craft_zana(:ana) |> return) - crafted_return
    zbey = (crafted |> craft_zana(:bey) |> return) - crafted_return
    zdom = (crafted |> craft_zana(:dom) |> return) - crafted_return
    zffb = (crafted |> craft_zana(:ffb) |> return) - crafted_return
    zleg = (crafted |> craft_zana(:leg) |> return) - crafted_return
    zper = (crafted |> craft_zana(:per) |> return) - crafted_return
    zwar = (crafted |> craft_zana(:war) |> return) - crafted_return

    %{
      base: map.value,
      # crafting
      alch: alch,
      chis: chis,
      vaal: vaal,
      frag: frag,
      # prophecies
      empr: empr,
      temp: temp,
      trap: trap,
      # sextants
      sexa: sexa,
      sexp: sexp,
      sexs: sexs,
      # zana
      zamb: zamb,
      zana: zana,
      zbey: zbey,
      zdom: zdom,
      zffb: zffb,
      ziiq: ziiq,
      zleg: zleg,
      zper: zper,
      zwar: zwar
    }
  end
end
