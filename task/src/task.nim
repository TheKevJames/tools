import std/enumerate
import std/options
import std/os
import std/sequtils
import std/streams
import std/strscans
import std/strutils
import std/tables
import std/times

import cligen

const
  maxTags = 3
  src = "~/Dropbox/vimwiki/todos.wiki"

type
  Details = tuple
    interval: TimeInterval
    next: Option[DateTime]
    shift: bool
  Filter = tuple
    data: string
    target: FilterTarget
  FilterTarget = enum
    ftSummary = "summary"
    ftTag = "tag"
  Tag = array[0..maxTags, string]
  Task = tuple
    details: Details
    id: int
    summary: string
    tag: Tag

func nonEmpty(details: Details): bool =
  details.next.isSome() or details.interval.days > 0 or details.shift

func raw(task: Task): string =
  result = task.summary
  if task.details.next.isSome():
    result = result & " {next: " & task.details.next.get().format("yyyy-MM-dd")
    if task.details.interval == 1.months:
      result = result & ", interval: monthly"
    elif task.details.interval == 0.days:
      discard
    else:
      result = result & ", interval: " & $task.details.interval.days
    if task.details.shift:
      result = result & ", shift: " & $task.details.shift
    result = result & "}"

func `$`(d: Details): string =
  if d.next.isSome():
    result = "Next: " & d.next.get().format("yyyy-MM-dd")
  if d.interval != 0.days:
    if d.interval == 1.months:
      result = result & ", " & "repeats monthly"
    else:
      result = result & ", " & "repeats " & $d.interval.days & " days"
    if d.shift:
      result = result & " after completion"
    else:
      result = result & " since last deadline"

func `$`(t: Tag): string =
  result = t[0][3..t[0].high-3]
  for i in 1..<maxTags:
    if t[i].len > 0:
      result = result & " > " & t[i][i+3..t[i].high-i-3]

func `$`(t: Task): string =
  result = $t.tag & "\t" & $t.id & ": " & t.summary
  if t.details.next.isSome():
    result = result & "\n\t" & $t.details

proc parseDetails(details: string): Details =
  func read(x: string): (string, Option[string]) =
    let pair = x.split(": ")
    (pair[0], some(pair[1]))

  if details.isEmptyOrWhitespace():
    return (interval: 0.days, next: none(DateTime), shift: false)

  let xs = details.split(", ").map(read).toTable()
  let shift = if xs.getOrDefault("shift").isSome():
    xs.getOrDefault("shift").get() == "true"
  else:
    false
  let next = if xs.getOrDefault("next").isSome():
    some(parse(xs.getOrDefault("next").get(), "yyyy-MM-dd"))
  else:
    none(DateTime)
  let interval = if xs.getOrDefault("interval").isSome():
    try:
      let days = xs.getOrDefault("interval").get().parseInt()
      days.days
    except ValueError:
      case xs.getOrDefault("interval").get():
        of "monthly":
          1.months
        of "weekly":
          7.days
        else:
          quit("interval must be numeric or 'monthly'")
  else:
    0.days

  # TODO: validation: if interval or shift is set without next, break
  (interval: interval, next: next, shift: shift)

proc parseFilter(filter: string): Option[Filter] =
  if filter.isEmptyOrWhitespace():
    return none(Filter)

  let split = filter.split("=")
  try:
    some((data: split[1], target: parseEnum[FilterTarget](split[0])))
  except ValueError:
    stderr.writeLine getCurrentExceptionMsg()
    quit("filter must be foo=bar where foo is a valid field name")

proc parseTask(data: string, id: int, tag: Tag): Task =
  var summary, detailStr: string
  let details = if scanf(data, "$+ {$+}", summary, detailStr):
    parseDetails(detailStr)
  else:
    parseDetails("")

  (details: details, id: id, summary: summary, tag: tag)

proc complete(task: Task): Option[Task] =
  if task.details.next.isSome() and task.details.interval != 0.days:
    var newTask = deepCopy(task)
    newTask.details.next = if task.details.shift:
      some(now() + task.details.interval)
    else:
      var next = task.details.next.get() + task.details.interval
      while next < now():
        next += task.details.interval
      some(next)

    echo "completed recurring task, next occurrence: " &
        newTask.details.next.get().format("yyyy-MM-dd")
    some(newTask)
  else:
    echo "completed task"
    none(Task)

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

proc filter(tasks: seq[Task], filter: Option[Filter]): seq[Task] =
  if filter.isNone():
    return tasks

  case filter.get().target:
  of ftSummary:
    result = tasks.filter(proc(x: Task): bool = (
        $x.summary).toLowerAscii.contains(filter.get().data))
  of ftTag:
    result = tasks.filter(proc(x: Task): bool = ($x.tag).toLowerAscii.contains(
        filter.get().data))

proc doList(filename: string, filter: string, includeFutureOffset: int,
    limit: int): seq[Task] =
  let tasks = load(filename).filter(parseFilter(filter))
  for i, task in tasks:
    if limit >= 0 and i > limit:
      break
    if task.details.next.isSome():
      if task.details.next.get() > now() + includeFutureOffset.days:
        continue
    result.add(task)

proc done(source: string = src, ids: seq[int]) =
  let tasks = doList(source, "", 365, -1).filter(proc(x: Task): bool = x.id in ids)
  for task in tasks:
    let completed = complete(task)
    if completed.isSome():
      source.expandTilde().absolutePath().writeFile(
        source.expandTilde().absolutePath().readFile.replace(task.raw(),
            completed.get().raw()))
    else:
      var xs = source.expandTilde().absolutePath().readFile().splitLines(keepEol = true)
      xs.delete(task.id)
      source.expandTilde().absolutePath().writeFile(xs.join())

proc due(source: string = src, includeFutureOffset: int = 3) =
  for task in doList(source, "", includeFutureOffset, -1):
    if task.details.next.isSome():
      echo task

proc edit(source: string = src) =
  discard execShellCmd("$EDITOR " & source)

proc list(source: string = src, filter: string = "",
    includeFutureOffset: int = 7, limit: int = -1) =
  for task in doList(source, filter, includeFutureOffset, limit):
    echo task

proc highpri(source: string = src) =
  for task in doList(source, "tag=highpri", 0, -1):
    echo task

proc triage(source: string = src) =
  for task in doList(source, "tag=triage", 365, -1):
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
