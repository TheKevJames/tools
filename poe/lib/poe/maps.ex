defmodule Poe.Maps.Mod do
	require Logger

	defstruct [:name, em: 0, iiq: 0, iir: 0, ps: 0, weight: 0]

	def bonus(mod) do
		# TODO: include iir
		(1 + mod.iiq/100.0) * (1 + mod.ps/100.0) * (1 + mod.em/50.0)
	end

	def from_map(%{"title" => %{"name" => name, "stat text raw" => raw_stats, "weight" => weight}}) do
		stats = Enum.reduce(String.split(raw_stats, "&lt;br&gt;"), %{}, fn stat, acc ->
			cond do
				matches = Regex.run(~r/(.*)%.*increased quantity of items/i, stat) ->
					# TODO: effective IIQ calcs:
					# https://www.reddit.com/r/pathofexile/comments/7zyyu8/the_formula_behind_iiq_and_how_many_drops_you_get/
					Map.put(acc, :iiq, String.to_integer(Enum.at(matches, 1)))
				matches = Regex.run(~r/(.*)%.*increased rarity of items/i, stat) ->
					Map.put(acc, :iir, String.to_integer(Enum.at(matches, 1)))
				matches = Regex.run(~r/\+(.*)%.*monster pack size/i, stat) ->
					Map.put(acc, :ps, String.to_integer(Enum.at(matches, 1)))
				true ->
					# TODO: any others to parse?
					# Logger.debug("ignoring mod stat: #{stat}")
					acc
			end
		end)
		%Poe.Maps.Mod{name: name, em: Map.get(stats, :em, 0), iiq: Map.get(stats, :iiq, 0), iir: Map.get(stats, :iiq, 0), ps: Map.get(stats, :ps, 0), weight: String.to_integer(weight)}
	end
end

defmodule Poe.Maps do
  require Logger
	alias Poe.Currency
	alias Poe.Maps.Mod

  def affix(tier) do
		tag = case tier do
			n when n > 10 -> "top_tier_map"
			n when n > 5 -> "mid_tier_map"
			n when n > 0 -> "low_tier_map"
			_ ->
				Logger.error("invalid map tier #{tier}")
				"low_tier_map"
		end
    prefixes = mods("default", 1) ++ mods(tag, 1)
    prefix = Enum.sum(Enum.map(prefixes, &(&1.weight * Mod.bonus(&1)))) / Enum.sum(Enum.map(prefixes, &(&1.weight)))
    suffixes = mods("default", 2) ++ mods(tag, 2)
    suffix = Enum.sum(Enum.map(suffixes, &(&1.weight * Mod.bonus(&1)))) / Enum.sum(Enum.map(suffixes, &(&1.weight)))
    (prefix + suffix) / 2.0
  end

  def fetch_mods(tag, generation) do
    api = "https://pathofexile.gamepedia.com/api.php"
    url = api
          |> URI.parse()
          |> Map.put(:query, URI.encode_query(
            action: "cargoquery",
            fields: "mods.name,mods.stat_text_raw,spawn_weights.weight",
            format: "json",
            join_on: "mods._pageID=spawn_weights._pageID",
            tables: "mods,spawn_weights",
            where: "mods.domain=5 AND mods.generation_type=#{generation} AND mods.name!=\"\" AND spawn_weights.tag=\"#{tag}\" AND spawn_weights.weight>0"
          ))
          |> URI.to_string()

    case HTTPoison.get(url) do
      {:ok, %{status_code: 200, body: body}} ->
        case Jason.decode!(body) do
          %{"error" => %{"info" => info}} ->
            Logger.error("cargoquery API returned error: #{info}")
          data -> Enum.map(Map.get(data, "cargoquery"), &Mod.from_map/1)
        end
      {:error, _} ->
        Logger.error("unknown error hitting cargoquery API")
    end
  end

  def mods(tag, generation) do
    key = {__MODULE__, tag, generation}
    case Poe.Cache.get(key) do
			{:hit, value} -> value
			{:miss} ->
        value = fetch_mods(tag, generation)
				Poe.Cache.put(key, value)
        value
    end
  end

	# TODO: get real numbers on this
	def base(tier) do
    Enum.at([0.63, 0.41, 0.45, 0.58, 0.61, 0.87, 1.03, 1.53, 1.91, 1.83, 3.3, 3.5, 5.7, 8.5, 12.6, 13.5, 15], tier - 1)
	end

	# apply crafting operations
  def alch(tier) do
		# TODO: verify alching rolls equally distributed 3-6 affixes
		base(tier) * :math.pow(affix(tier), 4.5)
  end

  def chis(tier) do
		base(tier) * Mod.bonus(%Mod{iiq: 20})
  end

  def frag(tier) do
		base(tier) * Mod.bonus(%Mod{iiq: 5})
  end

  def vaal(tier) do
    effects = [
      # nada
      base(tier),
      base(tier),
      # reroll
      base(tier) * :math.pow(affix(tier), 5),
      # uptier and reroll
      base(tier + 1) * :math.pow(affix(tier + 1), 5),
      # full reroll
      base(tier) * :math.pow(affix(tier), 8),
      base(tier) * :math.pow(affix(tier), 8),
      # unidentify
      base(tier) * Mod.bonus(%Mod{iiq: 30}),
      base(tier) * Mod.bonus(%Mod{iiq: 30}),
    ]
    (Enum.sum(effects) / length(effects))
  end

	def crafting_return(tier) do
		value = base(tier)
		alch_value = (alch(tier) - value) - Currency.cost(:alch)
		chis_value = (chis(tier) - value) - Currency.cost(:chis) * 4
		vaal_value = (vaal(tier) - value) - Currency.cost(:vaal)
		frag_value = (frag(tier) - value) - Currency.cost(:frag)

		# TODO: sextants, prophecies (tempest, extra monsters, bountiful traps), shaped, zanas, scarabs
		# refs:
		#   https://imgur.com/1EsuAEP
		#   https://i.imgur.com/AsOZpGt.png
		#   https://docs.google.com/spreadsheets/d/1Mdl01Fc4DycxeXrKxj_R0rIybmQVowEc0TKNtLzpLGM/edit#gid=354958689
		#   https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/
		#   https://docs.google.com/spreadsheets/d/1fIs8sdvgZG7iVouPdtFkbRx5kv55_xVja8l19yubyRU/htmlview?usp=sharing%3Cbr%3E&pru=AAABd0d78Os*Qj2_YGoUjIwCB9669xsZCw#
		%{alch: alch_value, chis: chis_value, vaal: vaal_value, frag: frag_value}
	end
end
