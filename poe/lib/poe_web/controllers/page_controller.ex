defmodule PoeWeb.PageController do
  require Logger
  use PoeWeb, :controller

  def bonus(iiq, ps, em) do
    # TODO: include iir
    (1 + iiq/100.0) * (1 + ps/100.0) * (1 + em/100.0)
  end

  def alch(tier, value) do
    # TODO: migrate fetch() to elixir
    mult = [2.259, 2.225, 2.245]
    # TODO: does t16 count as top tier for affixes?
    value * Enum.at(mult, min(div(tier, 5), 2))
  end

  def chis(_tier, value) do
    value * bonus(20, 0, 0)
  end

  def frag(_tier, value) do
    value * bonus(5, 0, 0)
  end

  def vaal(tier, value) do
    # TODO: migrate fetch() to elixir
    # TODO: actual numbers for T15 -> Vaal Temple reroll
    affix = [1.197, 1.195, 1.199, 1.21]
    effects = [
      # nada
      0, 0,
      # reroll, maybe uptier
      :math.pow(Enum.at(affix, div(tier, 5)), 5), :math.pow(Enum.at(affix, div(tier + 1, 5)), 5),
      # full reroll
      :math.pow(Enum.at(affix, div(tier, 5)), 8), :math.pow(Enum.at(affix, div(tier, 5)), 8),
      # unidentify
      bonus(30, 0, 0), bonus(30, 0, 0),
    ]
    value * (Enum.sum(effects) / length(effects))
  end

  def calc() do
    # TODO: fetch live values
    alch_cost = 1.0 / 6.1
    chis_cost = 1.0 / 2.6
    frag_cost = 1.0 / 3.8
    vaal_cost = 1.0 / 1.5

    # TODO: get real numbers on this
    base = [0.63, 0.41, 0.45, 0.58, 0.61, 0.87, 1.03, 1.53, 1.91, 1.83, 3.3, 3.5, 5.7, 8.5, 12.6, 13.5]

    for {value, tier} <- Enum.with_index(base) do
      do_alch = alch(tier, value) - value > alch_cost
      do_chis = chis(tier, value) - value > chis_cost * 4
      do_vaal = vaal(tier, value) - value > vaal_cost
      do_frag = frag(tier, value) - value > frag_cost

      # TODO: sextants, prophecies (tempest, extra monsters, bountiful traps), shaped, zanas
      # refs:
      #   https://imgur.com/1EsuAEP
      #   https://i.imgur.com/AsOZpGt.png
      #   https://docs.google.com/spreadsheets/d/1Mdl01Fc4DycxeXrKxj_R0rIybmQVowEc0TKNtLzpLGM/edit#gid=354958689
      #   https://www.reddit.com/r/pathofexile/comments/a83vm7/new_players_guide_to_crafting_maps/
      #   https://docs.google.com/spreadsheets/d/1fIs8sdvgZG7iVouPdtFkbRx5kv55_xVja8l19yubyRU/htmlview?usp=sharing%3Cbr%3E&pru=AAABd0d78Os*Qj2_YGoUjIwCB9669xsZCw#
      %{alch: do_alch, chis: do_chis, vaal: do_vaal, frag: do_frag}
    end
  end

  def index(conn, _params) do
    render(conn, "index.html", calc: calc())
  end
end
