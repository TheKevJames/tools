import std/enumerate
import std/options
import std/os
import std/sequtils
import std/strutils
import std/streams

import cligen

from task/cmd import nil
import task/types

const
  src = "~/Dropbox/vimwiki/todos.wiki"

proc load(filename: string): seq[Task] =
  var file: FileStream

  try:
    file = openFileStream(filename.expandTilde().absolutePath(), fmRead)
  except:
    stderr.writeLine getCurrentExceptionMsg()
    quit("cannot open the file " & filename)

  defer: file.close()

  var
    level: int
    line: string
    tag: Tag

  for lineno, line in enumerate(file.lines):
    if line.startsWith("=="):
      level = line.splitWhitespace(maxsplit = 1)[0].len - 2
      tag[level] = line
      for x in level+1..<maxTags:
        tag[x] = ""
    elif line.startsWith("* "):
      result.add(line[2..line.high].parseTask(lineno, tag))

proc done(source: string = src, ids: seq[int]) =
  let tasks = cmd.list(load(source), "", 365, -1).filter(proc(x: Task): bool = x.id in ids)
  for task in tasks:
    let completed = task.complete()
    if completed.isSome():
      source.expandTilde().absolutePath().writeFile(
        source.expandTilde().absolutePath().readFile.replace(task.raw(),
            completed.get().raw()))
    else:
      var xs = source.expandTilde().absolutePath().readFile().splitLines(keepEol = true)
      xs.delete(task.id)
      source.expandTilde().absolutePath().writeFile(xs.join())

proc due(source: string = src, includeFutureOffset: int = 3) =
  for task in cmd.list(load(source), "", includeFutureOffset, -1):
    if task.details.next.isSome():
      echo task

proc edit(source: string = src) =
  discard execShellCmd("$EDITOR " & source)

proc highpri(source: string = src) =
  for task in cmd.list(load(source), "tag=highpri", 0, -1):
    echo task

proc list(source: string = src, filter: string = "",
    includeFutureOffset: int = 7, limit: int = -1) =
  for task in cmd.list(load(source), filter, includeFutureOffset, limit):
    echo task

proc triage(source: string = src) =
  for task in cmd.list(load(source), "tag=triage", 365, -1):
    echo task

when isMainModule:
  dispatchMulti(
    [done],
    [due],
    [edit],
    [highpri],
    [list, help = {
      "filter": "foo=bar",
      "includeFutureOffset": "include future tasks within n days"}],
    [triage])
