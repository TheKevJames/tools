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
    namespace = 'namespace'
    tag = 'tag'
    owner = 'owner'
    link = 'link'
    priority = 'priority'
    size = 'size'


# Filter values are compared lowercased. `fold` is Python's str.lower,
# registered by db.connect: SQLite's lower() only folds ASCII. Namespaces and
# tags are stored lowercased.
COLUMNS = {
    Target.summary: 'fold(summary)',
    Target.namespace: 'namespace',
    Target.tag: 'tag',
    Target.owner: "fold(coalesce(owner, ''))",
    Target.link: "fold(coalesce(link, ''))",
    Target.priority: "coalesce(priority, '')",
    Target.size: "coalesce(size, '')",
}


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
        column = COLUMNS[self.target]
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


# Ids repeat across namespaces, so every order ends on both.
ORDER_BY = {
    SortOrder.ident: 'id, namespace',
    SortOrder.due: 'next IS NOT NULL, next, id, namespace',
    SortOrder.tag: (
        f"namespace != '{schema.DEFAULT}', namespace,"
        f" tag != '{schema.TRIAGE}', tag, id"
    ),
    SortOrder.created: 'created, id, namespace',
    SortOrder.updated: 'updated DESC, id, namespace',
}


def compile_(
    filter_: str,
    days: int,
    limit: int,
    order: SortOrder,
    *,
    scheduled: bool = False,
) -> tuple[str, dict[str, object]]:
    """The WHERE, ORDER BY, and LIMIT clauses selecting tasks, and params."""
    clauses: list[str] = []
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

    sql = f' WHERE {" AND ".join(clauses)}' if clauses else ''
    sql += f' ORDER BY {ORDER_BY[order]}'
    if limit >= 0:
        sql += ' LIMIT :limit'
        params['limit'] = limit
    return sql, params
