defmodule Poe.Market do
  require Logger

  def cost(name) do
    key = {__MODULE__, name}
    case Poe.Cache.get(key) do
      {:hit, value} -> value
      {:miss} ->
        # TODO: fetch live values
        value = case name do
          :alch -> 1.0 / 6.1
          :chis -> 1.0 / 2.6
          :frag -> 1.0 / 3.8
          :vaal -> 1.0 / 1.5
          :sexs -> 1.0 / 1.4
          :sexp -> 1.0 / 1.2
          :sexa -> 1.2 / 1.0
          :sexe -> 43.8 / 1.0
          _ -> 0.0
        end
        Poe.Cache.put(key, value)
        value
    end
  end
end
