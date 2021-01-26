defmodule Poe.Market do
  require Logger

  def cost(name) do
    key = {__MODULE__, name}

    case Poe.Cache.get(key) do
      {:hit, value} ->
        value

      {:miss} ->
        # TODO: fetch live values from poe.ninja
        value =
          case name do
            :alch -> 1.0 / 6.5
            :chis -> 1.0 / 2.6
            :frag -> 1.0 / 3.5
            # TODO: only on currency.poe.trade, not ninja: why?
            :pdus -> 1.0 / 300.0
            :sexa -> 1.0 / 1.0
            :sexp -> 1.0 / 1.2
            :sexs -> 1.0 / 1.2
            # TODO: all the same?
            :empr -> 1.0
            # TODO: all the same?
            :temp -> 1.0
            :trap -> 1.3
            :vaal -> 1.0 / 1.5
            _ -> 0.0
          end

        Poe.Cache.put(key, value)
        value
    end
  end
end
