defmodule PoeWeb.StrongboxesController do
  use PoeWeb, :controller

  def index(conn, _params) do
    render(conn, "index.html")
  end
end
