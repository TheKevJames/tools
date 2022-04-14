import std/options
import std/sequtils
import std/strutils
import std/times

import types

proc filter(tasks: seq[Task], filter: Filter): seq[Task] =
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

proc list*(tasks: seq[Task], filters: string, includeFutureOffset: int, limit: int): seq[Task] =
  for i, task in parseFilter(filters).foldl(filter(a, b), tasks):
    if limit >= 0 and i > limit:
      break
    if task.details.next.isSome():
      if task.details.next.get() > now() + includeFutureOffset.days:
        continue
    result.add(task)
