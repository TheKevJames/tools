import std/options
import std/sequtils
import std/strutils
import std/times

import types

proc filter(tasks: seq[Task], filter: Option[Filter]): seq[Task] =
  if filter.isNone():
    return tasks

  case filter.get().target:
  of ftSrc:
    result = tasks.filter(proc(x: Task): bool = ($x.link.ftitle).toLowerAscii.contains(filter.get().data))
  of ftSummary:
    result = tasks.filter(proc(x: Task): bool = ($x.summary).toLowerAscii.contains(filter.get().data))
  of ftTag:
    result = tasks.filter(proc(x: Task): bool = ($x.tag).toLowerAscii.contains(filter.get().data))

proc list*(tasks: seq[Task], filter: string, includeFutureOffset: int, limit: int): seq[Task] =
  for i, task in tasks.filter(parseFilter(filter)):
    if limit >= 0 and i > limit:
      break
    if task.details.next.isSome():
      if task.details.next.get() > now() + includeFutureOffset.days:
        continue
    result.add(task)
