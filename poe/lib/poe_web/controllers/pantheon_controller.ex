defmodule PoeWeb.PantheonController do
  require Logger
  use PoeWeb, :controller
  alias Poe.Pantheon

  def fetch() do
    Pantheon.fetch()
  end

  def index(conn, _params) do
    render(conn, "index.html", data: fetch())
  end
end
