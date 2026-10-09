"""Selecting and ordering tasks: filters and sort orders, compiled to SQL."""

import datetime
import enum
import re
from collections.abc import Iterator
from typing import Self

import pydantic

from . import schema


class Target(enum.StrEnum):
    summary = 'summary'
    tag = 'tag'
    owner = 'owner'
    link = 'link'
    priority = 'priority'
    size = 'size'


# Filter values are compared lowercased. `fold` is Python's str.lower,
# registered by db.connect: SQLite's lower() only folds ASCII.
COLUMNS = {
    Target.summary: 'fold(summary)',
    Target.owner: "fold(coalesce(owner, ''))",
    Target.link: "fold(coalesce(link, ''))",
    Target.priority: "coalesce(priority, '')",
    Target.size: "coalesce(size, '')",
}

# Any single segment or any path from the root matches, so `tag=build` and
# `tag=bakery/build` both select bakery/build. Tags are stored lowercased.
TAG_EQUALS = (
    "(instr({v}, '/') = 0 AND instr('/' || tag || '/', '/' || {v} || '/') > 0)"
    " OR tag = {v} OR substr(tag, 1, length({v}) + 1) = {v} || '/'"
)


class Filter(pydantic.BaseModel, extra='forbid'):
    data: str
    negate: bool
    contains: bool
    target: Target

    @classmethod
    def parse(cls, raw: str) -> Iterator[Self]:
        for filter_ in raw.split(','):
            if not filter_.strip():
                continue

            match = re.match(
                r'(?P<target>[^!=~]+)(?P<op>!?[=~])(?P<data>.*)', filter_
            )
            assert match, f'{filter_} is not a valid filter'
            op = match.group('op')

            yield cls(
                data=match.group('data').lower(),
                negate=op.startswith('!'),
                contains=op.endswith('~'),
                target=Target(match.group('target')),
            )

    def sql(self, param: str) -> str:
        """A boolean expression comparing against `data`, bound to `param`."""
        value = f':{param}'
        if self.target == Target.tag and not self.contains:
            clause = TAG_EQUALS.format(v=value)
        else:
            # Every segment and root path is a substring of the full tag.
            column = (
                'tag' if self.target == Target.tag else COLUMNS[self.target]
            )
            if self.contains:
                clause = f'instr({column}, {value}) > 0'
            else:
                clause = f'{column} = {value}'
        return f'NOT ({clause})' if self.negate else f'({clause})'


class SortOrder(enum.StrEnum):
    ident = 'id'
    due = 'due'
    tag = 'tag'
    created = 'created'
    updated = 'updated'


# char(1) sorts below every character a tag segment may hold, so a section's
# children sort directly after it (bakery, bakery/build, bakery-x).
ORDER_BY = {
    SortOrder.ident: 'id',
    SortOrder.due: 'next IS NOT NULL, next, id',
    SortOrder.tag: (
        f"tag != '{schema.TRIAGE}', replace(tag, '/', char(1)), id"
    ),
    SortOrder.created: 'created, id',
    SortOrder.updated: 'updated DESC, id',
}


def compile_(
    filter_: str,
    days: int,
    limit: int,
    order: SortOrder,
    *,
    scheduled: bool = False,
    done: bool = False,
) -> tuple[str, dict[str, object]]:
    """
    The WHERE, ORDER BY, and LIMIT clauses selecting tasks, and params.

    Selects either open tasks or, with `done`, only done ones.
    """
    clauses = ['done IS NOT NULL' if done else 'done IS NULL']
    params: dict[str, object] = {}
    for i, filter_part in enumerate(Filter.parse(filter_)):
        clauses.append(filter_part.sql(f'filter{i}'))
        params[f'filter{i}'] = filter_part.data
    if days >= 0:
        target = datetime.date.today() + datetime.timedelta(days=days)
        clauses.append('(next IS NULL OR next <= :target)')
        params['target'] = target.isoformat()
    if scheduled:
        clauses.append('next IS NOT NULL')

    sql = f' WHERE {" AND ".join(clauses)}'
    sql += f' ORDER BY {ORDER_BY[order]}'
    if limit >= 0:
        sql += ' LIMIT :limit'
        params['limit'] = limit
    return sql, params
