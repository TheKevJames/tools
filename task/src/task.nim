import std/[enumerate, options, os, sequtils, sets, strutils, times]
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
    if line.startsWith("# TODOs"):
      title = line.splitWhitespace()[2]
    elif line.startsWith("##"):
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

proc save(tasks: seq[Task]) =
  for fname in tasks.mapIt(it.link.fname).deduplicate:
    echo "Writing to " & fname
    var xs = tasks.filterIt(it.link.fname == fname)

    var f = open(fname, fmWrite)
    f.writeLine("# TODOs: " & xs[0].link.ftitle)

    var lasttag: Tag
    for task in xs:
      if lasttag != task.tag:
        # always keep a triage section at the top
        if lasttag.countIt(it.len > 0) == 0:
          if $task.tag != "Triage":
            f.writeLine("")
            f.writeLine("## Triage")

        f.writeLine("")
        f.writeLine(task.tag.raw())
        lasttag = task.tag

      f.writeLine("* " & task.raw())

proc delay(ids: seq[string], days: int = 0) =
  let tasks = cmd.list(load(), "", 365, -1).filter(proc(x: Task): bool = $x.link in ids)
  for task in tasks:
    let delayed = task.postpone(days)
    if delayed.isSome():
      echo "delayed task, next occurrence: " &
        delayed.get().details.next.get().format("yyyy-MM-dd")

      task.link.fname.writeFile(
        task.link.fname.readFile.replace(task.raw(), delayed.get().raw()))
    else:
      echo "cannot delay task: " & $task.link
      echo "periodic tasks with shift=false cannot be delayed"

proc done(ids: seq[string], ago: int = 0) =
  let tasks = cmd.list(load(), "", 365, -1).filter(proc(x: Task): bool = $x.link in ids)
  for task in tasks:
    let completed = task.complete(ago)
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

proc due(filter: string = "", limit: int = -1) =
  for task in cmd.listWithNext(load(), filter, 0, limit):
    echo task

proc edit(idxs: seq[int]) =
  let conf = config.load()
  if idxs.len == 0:
    for idx, src in conf.srcs:
      echo $idx & "\t" & src
  else:
    for idx in idxs:
      discard execShellCmd("$EDITOR " & conf.srcs[idx])

proc highpri(filter: string = "", includeFutureOffset: int = -1, limit: int = -1) =
  for task in cmd.list(load(), filter & ",tag=highpri", includeFutureOffset, limit):
    echo task

proc list(filter: string = "", includeFutureOffset: int = 7, limit: int = -1) =
  for task in cmd.list(load(), filter, includeFutureOffset, limit):
    echo task

proc rewrite() =
  let tasks = cmd.list(load(), "", -1, -1)
  save(tasks)

proc soon(filter: string = "", includeFutureOffset: int = 3, limit: int = -1) =
  for task in cmd.listWithNext(load(), filter, includeFutureOffset, limit):
    echo task

proc triage(filter: string = "", includeFutureOffset: int = -1, limit: int = -1) =
  for task in cmd.list(load(), filter & ",tag=triage", includeFutureOffset, limit):
    echo task

when isMainModule:
  dispatchMulti(
    [delay, help = {
      "days": "delay task by n days"}],
    [done, help = {
      "ago": "mark task as completed n days ago"}],
    [due, help = {
      "filter": "foo=bar,baz=buuq,..."}],
    [edit],
    [highpri, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}],
    [list, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}],
    [rewrite],
    [soon, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}],
    [triage, help = {
      "filter": "foo=bar,baz=buuq,...",
      "includeFutureOffset": "include future tasks within n days"}])
