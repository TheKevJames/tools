import std/enumerate
import std/options
import std/os
import std/sequtils
import std/strutils
import std/times

import cligen

import task/types
from task/cmd import nil
from task/config import nil

proc load(filename: string): seq[Task] =
  var
    level: int
    title: string
    tag: Tag

  for lineno, line in enumerate(filename.lines):
    if line.startsWith("= TODOs"):
      title = line.splitWhitespace()[2]
    elif line.startsWith("=="):
      level = line.splitWhitespace(maxsplit=1)[0].len - 2
      tag[level] = line
      for x in level+1..<maxTags:
        tag[x] = ""
    elif line.startsWith("* "):
      result.add(line[2..line.high].parseTask(title, filename, lineno, tag))

proc load(): seq[Task] =
  let conf = config.load()
  for idx, src in conf.srcs:
    result = result & load(src)

proc done(ids: seq[string]) =
  let tasks = cmd.list(load(), "", 365, -1).filter(proc(x: Task): bool = $x.link in ids)
  for task in tasks:
    let completed = task.complete()
    if completed.isSome():
      echo "completed recurring task, next occurrence: " &
        completed.get().details.next.get().format("yyyy-MM-dd")

      task.link.fname.writeFile(
        task.link.fname.readFile.replace(task.raw(), completed.get().raw()))
    else:
      echo "completed task"

      var xs = task.link.fname.readFile().splitLines(keepEol = true)
      xs.delete(task.link.lineno)
      task.link.fname.writeFile(xs.join())

proc due(filter: string = "", includeFutureOffset: int = 3) =
  for task in cmd.list(load(), filter, includeFutureOffset, -1):
    if task.details.next.isSome():
      echo task

proc edit(idxs: seq[int]) =
  let conf = config.load()
  if idxs.len == 0:
    for idx, src in conf.srcs:
      echo $idx & "\t" & src
  else:
    for idx in idxs:
      discard execShellCmd("$EDITOR " & conf.srcs[idx])

proc highpri(filter: string = "") =
  for task in cmd.list(load(), filter & ",tag=highpri", 0, -1):
    echo task

proc list(filter: string = "", includeFutureOffset: int = 7, limit: int = -1) =
  for task in cmd.list(load(), filter, includeFutureOffset, limit):
    echo task

proc triage(filter: string = "") =
  for task in cmd.list(load(), filter & ",tag=triage", 365, -1):
    echo task

when isMainModule:
  dispatchMulti(
    [done],
    [due, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}],
    [edit],
    [highpri, help = {
      "filter": "foo=bar,baz=buuq,..."}],
    [list, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}],
    [triage, help = {
      "filter": "foo=bar,baz=buuq,..."}])
