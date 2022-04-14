import std/[options, times]
import filter
import types

proc list*(tasks: seq[Task], filter: string, includeFutureOffset: int, limit: int): seq[Task] =
  for i, task in parseFilter(filter).applyFilter(tasks):
    if limit >= 0 and i > limit:
      break

    if includeFutureOffset >= 0 and task.details.next.isSome():
      if task.details.next.get() > now() + includeFutureOffset.days:
        continue

    result.add(task)
