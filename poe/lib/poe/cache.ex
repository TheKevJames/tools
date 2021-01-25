# TODO: cache invalidation
defmodule Poe.Cache do
  use GenServer

  @table __MODULE__

  def init(args) do
    :ets.new(@table, [
      :set,
      :public,
      :named_table,
      {:read_concurrency, true},
      {:write_concurrency, true}
    ])

    {:ok, args}
  end

  def start_link(args) do
    GenServer.start_link(__MODULE__, args, name: __MODULE__)
  end

  def get(key) do
    case :ets.lookup(@table, key) do
      [] -> {:miss}
      [{^key, value}] -> {:hit, value}
    end
  end

  def put(key, value) do
    :ets.insert(@table, {key, value})
  end
end
