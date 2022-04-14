import std/[json, sequtils, strutils, os, osproc]

type
  Config* = object
    srcs*: seq[string]

proc load*(): Config =
  let xs = execProcess(quoteShellCommand(
    ["/opt/local/bin/nvim",
     "+redir! >/dev/stdout",
     "+echo g:vimwiki_list",
     "+qall"]),
    options = {poEvalCommand})

  # TODO: consider tree searching for todo files
  let srcs = xs.splitLines
    .filter(proc(x: string): bool = x.startsWith("[{'path"))[0]
    .replace("'", "\"").parseJson().getElems()
    .map(proc(x: JsonNode): string = x{"path"}.getStr())
    .map(proc(x: string): string = x.expandTilde().absolutePath() & "/todos.wiki")

  Config(srcs: srcs)
