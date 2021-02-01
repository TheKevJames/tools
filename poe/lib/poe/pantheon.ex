defmodule Poe.Pantheon do
  require Logger
  alias Poe.Api.Wiki
  alias Poe.Maps

  def fetch() do
    Wiki.pantheon_souls()
    |> Enum.reduce(%{}, fn %{
                             "title" => %{
                               "id" => id,
                               "stat text" => raw_text,
                               "target area id" => raw_map
                             }
                           },
                           acc ->
      map_name =
        Regex.replace(~r/([A-Z])/, raw_map |> String.replace_leading("MapWorlds", ""), " \\1")
        |> String.trim()

      map =
        case Map.get(Maps.fetch(), map_name) do
          nil -> map_name
          x -> "#{map_name} (Tier #{x})"
        end

      text =
        Regex.replace(~r/\[\[(?:.*?\|)?(.*?)\]\]/, raw_text, "\\1")
        |> String.replace("&lt;br&gt;", "<br/>")

      Map.put(acc, id, Map.put(Map.get(acc, id, %{}), map, text))
    end)
  end
end
