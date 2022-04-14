import std/[sequtils, strutils]
import types

type
  Filter* = tuple
    data: string
    target: FilterTarget

  FilterTarget* = enum
    ftSrc = "src"
    ftSummary = "summary"
    ftTag = "tag"

proc parseFilter*(data: string): seq[Filter] =
  for filter in data.split(","):
    if filter.isEmptyOrWhitespace:
      continue

    let split = filter.split("=")

    try:
      result.add((data: split[1], target: parseEnum[FilterTarget](split[0])))
    except ValueError:
      stderr.writeLine getCurrentExceptionMsg()
      quit("filter must be foo=bar where foo is a valid field name")

proc apply(tasks: seq[Task], filter: Filter): seq[Task] =
  case filter.target:
    of ftSrc:
      result = tasks.filter(
        proc(x: Task): bool = ($x.link.ftitle).toLowerAscii.contains(filter.data))
    of ftSummary:
      result = tasks.filter(
        proc(x: Task): bool = ($x.summary).toLowerAscii.contains(filter.data))
    of ftTag:
      result = tasks.filter(
        proc(x: Task): bool = ($x.tag).toLowerAscii.contains(filter.data))

proc applyFilter*(filter: seq[Filter], tasks: seq[Task]): seq[Task] =
  filter.foldl(apply(a, b), tasks)
