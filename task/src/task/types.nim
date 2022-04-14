import std/options
import std/sequtils
import std/strscans
import std/strutils
import std/tables
import std/times

const
  maxTags* = 3

type
  Details = tuple
    interval: TimeInterval
    next: Option[DateTime]
    shift: bool

  Filter* = tuple
    data: string
    target: FilterTarget

  FilterTarget* = enum
    ftSrc = "src"
    ftSummary = "summary"
    ftTag = "tag"

  Tag* = array[0..maxTags, string]

  Task* = tuple
    details: Details
    link: TaskLink
    summary: string
    tag: Tag

  TaskLink* = tuple
    fname: string
    ftitle: string
    lineno: int

func `$`*(d: Details): string =
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

func `$`*(l: TaskLink): string = l.ftitle[0].toLowerAscii & $l.lineno

func `$`*(t: Tag): string =
  result = t[0][3..t[0].high-3]
  for i in 1..<maxTags:
    if t[i].len > 0:
      result = result & " > " & t[i][i+3..t[i].high-i-3]

func `$`*(t: Task): string =
  result = $t.tag & "\t" & $t.link & ": " & t.summary
  if t.details.next.isSome():
    result = result & "\n\t" & $t.details

# TODO: why is this not able to be func'd?
proc complete*(task: Task): Option[Task] =
  if task.details.next.isSome() and task.details.interval != 0.days:
    var newTask = deepCopy(task)
    newTask.details.next = if task.details.shift:
      some(now() + task.details.interval)
    else:
      var next = task.details.next.get() + task.details.interval
      while next <= now():
        next += task.details.interval
      some(next)

    some(newTask)
  else:
    none(Task)

func raw*(task: Task): string =
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
          quit("interval must be numeric or 'monthly'/'weekly'")
  else:
    0.days

  # TODO: validation: if interval or shift is set without next, break
  (interval: interval, next: next, shift: shift)

proc parseFilter*(filter: string): Option[Filter] =
  if filter.isEmptyOrWhitespace():
    return none(Filter)

  let split = filter.split("=")
  try:
    some((data: split[1], target: parseEnum[FilterTarget](split[0])))
  except ValueError:
    stderr.writeLine getCurrentExceptionMsg()
    quit("filter must be foo=bar where foo is a valid field name")

proc parseTask*(data: string, filetitle: string, filename: string, lineno: int, tag: Tag): Task =
  var summary, detailStr: string
  let details = if scanf(data, "$+ {$+}", summary, detailStr):
    parseDetails(detailStr)
  else:
    parseDetails("")

  (details: details, link: (fname: filename, ftitle: filetitle, lineno: lineno), summary: summary, tag: tag)
