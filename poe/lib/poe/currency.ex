defmodule Poe.Currency do
  require Logger

  def cost(currency) do
    key = {__MODULE__, currency}
    case Poe.Cache.get(key) do
      {:hit, value} -> value
      {:miss} ->
        # TODO: fetch live values
        value = case currency do
          :alch -> 1.0 / 6.1
          :chis -> 1.0 / 2.6
          :frag -> 1.0 / 3.8
          :vaal -> 1.0 / 1.5
          _ -> 0.0
        end
        Poe.Cache.put(key, value)
        value
    end
  end
end
