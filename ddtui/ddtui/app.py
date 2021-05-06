import asyncio
import curses
import dataclasses
import enum
import os
import pathlib
import shelve
import time
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import aiohttp


API = 'https://api.datadoghq.com/api/v1'
HEADERS = {
    'Content-Type': 'application/json',
    'DD-API-KEY': os.environ['DD_API_KEY'],
    'DD-APPLICATION-KEY': os.environ['DD_APP_KEY'],
}
PARAMS: Dict[str, Any] = {}


class Ast:
    eq: Optional[str] = None
    add: Optional[Tuple['Ast', 'Ast']] = None
    mult: Optional[Tuple['Ast', 'Ast']] = None

    def __init__(self, op: str, lhs: Union[str, 'Ast'],
                 rhs: Optional['Ast'] = None) -> None:
        if op == '=':
            self.eq = cast(str, lhs)
        elif op == '+':
            self.add = (cast(Ast, lhs), cast(Ast, rhs))
        elif op == '*':
            self.mult = (cast(Ast, lhs), cast(Ast, rhs))
        else:
            assert False, f'invalid AST node {op}, {lhs}, {rhs}'

    @classmethod
    def parse(cls, s: str) -> 'Ast':
        # Splits based on brackets, +, and *. This should be a CFG.
        for i, c in enumerate(s):
            if c == '(':
                x = s[i:].find(')')
                rem = s[i + x + 1:].strip()
                if rem:
                    return cls(rem[0], cls.parse(s[i + 1:i + x]),
                               cls.parse(rem[1:]))

                value = cls.parse(s[i + 1:i + s[i:].find(')')])
                if isinstance(value, str):
                    return cls('=', value)
                return value

            if c in {'+', '*'}:
                return cls(c, cls.parse(s[:i]), cls.parse(s[i + 1:]))

        return cls('=', s.replace('MASK', '()').strip())

    async def visit(self, s: aiohttp.ClientSession) -> Dict[str, float]:
        if self.eq:
            resp = await s.get(f'{API}/query',
                               params={**PARAMS, 'query': self.eq})
            series = (await resp.json())['series']
            if not series:
                return {}
            return dict(series[0]['pointlist'])

        if self.add:
            lhs = await self.add[0].visit(s)
            rhs = await self.add[1].visit(s)
            return {k: lhs.get(k, 0.) + rhs.get(k, 0)
                    for k in set(lhs) | set(rhs)}

        if self.mult:
            lhs = await self.mult[0].visit(s)
            rhs = await self.mult[1].visit(s)
            return {k: lhs.get(k, 0.) * rhs.get(k, 0)
                    for k in set(lhs) | set(rhs)}

        raise Exception(f'visiting unsupported AST node {self}')


@dataclasses.dataclass
class SloResult:
    name: str
    value: float

    @classmethod
    async def from_metric(cls, data: Dict[str, Any],
                          s: aiohttp.ClientSession) -> 'SloResult':
        queries = data['query']['numerator'].strip()
        ast = Ast.parse(queries.replace('()', 'MASK'))
        numerators = await ast.visit(s)

        queries = data['query']['denominator'].strip()
        ast = Ast.parse(queries.replace('()', 'MASK'))
        denominators = await ast.visit(s)

        points = {k: numerators[k] / denominators[k]
                  for k in set(numerators) & set(denominators)}
        result = 100. * sum(points.values()) / len(points)
        return SloResult(data['name'], result)

    @classmethod
    async def from_monitor(cls, monitor: str,
                           s: aiohttp.ClientSession) -> 'SloResult':
        resp = await s.get(f'{API}/monitor/{monitor}')
        payload = await resp.json()

        query, _gt, target_str = payload['query'].rsplit(' ', 2)
        target = float(target_str)
        _agg, query = query.split(':', 1)

        resp = await s.get(f'{API}/query', params={**PARAMS, 'query': query})
        monitors = [(sum((x[1] or 0.) > target for x in series['pointlist'])
                     / len(series['pointlist']))
                    for series in (await resp.json())['series']]
        result = 100. - sum(monitors) / len(monitors)

        return SloResult(payload['name'], result)


@dataclasses.dataclass
class Slo:
    name: str
    results: List[SloResult]
    updated: float

    @classmethod
    async def fetch(cls, slos: shelve.Shelf, data: Dict[str, Any],
                    s: aiohttp.ClientSession) -> None:
        if data['id'] in slos and time.time() - slos[data['id']].updated < 60:
            return

        results = []
        if data['type'] == 'metric':
            results.append(await SloResult.from_metric(data, s))
        elif data['type'] == 'monitor':
            for monitor in data['monitor_ids']:
                results.append(await SloResult.from_monitor(monitor, s))
        else:
            assert False, f'unsupported SLO type {data["type"]}'

        slos[data['id']] = Slo(data['name'], results, time.time())


async def poll(slos: shelve.Shelf) -> None:
    """Poll loop: grab each slow for this week hourly."""
    async with aiohttp.ClientSession(headers=HEADERS,
                                     raise_for_status=True) as s:
        resp = await s.get(f'{API}/slo')
        data = (await resp.json())['data']

        while True:
            PARAMS['to'] = int(time.time()) - 600
            PARAMS['from'] = PARAMS['to'] - 60 * 60 * 24 * 7

            try:
                await asyncio.gather(*[Slo.fetch(slos, d, s) for d in data])
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    try:
                        delay = int(e.headers['x-ratelimit-reset'])
                    except KeyError:
                        raise e from None
                    else:
                        await asyncio.sleep(delay)
            else:
                await asyncio.sleep(60 * 60)


async def readio(stdscr: 'curses._CursesWindow',
                 q: 'asyncio.Queue[str]') -> None:
    while True:
        k = stdscr.getch(0, 0)
        if k != -1:
            await q.put(chr(k))
            continue
        # TODO: faster without polling too often
        await asyncio.sleep(1)


async def tick(q: 'asyncio.Queue[str]') -> None:
    for _ in range(5):
        await q.put(' ')
        await asyncio.sleep(1)

    while True:
        await q.put(' ')
        await asyncio.sleep(10)


class Sort(enum.Enum):
    NAME = 'n'
    VALUE = 'v'


class State:
    def __init__(self) -> None:
        self.sort = Sort.NAME
        self._reverse = False

    @property
    def key(self) -> Callable[[Slo], Union[str, float]]:
        if self.sort is Sort.NAME:
            return lambda x: x.name
        if self.sort is Sort.VALUE:
            return lambda xs: min(x.value for x in xs.results)
        assert False, f'invalid Sort value {self.sort}'
        return lambda _: 0.

    @property
    def reverse(self) -> bool:
        if self.sort is Sort.VALUE:
            return not self._reverse
        return self._reverse

    def handle(self, key: str) -> None:
        if key in {'n', 'v'}:
            self.sort = Sort(key)
        elif key in {'r'}:
            self._reverse = not self._reverse

    def render_bar(self, stdscr: 'curses._CursesWindow', row: int) -> None:
        stdscr.addstr(row, 0, 'Sort:', curses.A_DIM)

        if self.sort == Sort.NAME:
            stdscr.attron(curses.A_BOLD)
        stdscr.addstr(row, 6, '[n]ame')
        stdscr.attroff(curses.A_BOLD)

        if self.sort == Sort.VALUE:
            stdscr.attron(curses.A_BOLD)
        stdscr.addstr(row, 13, '[v]alue')
        stdscr.attroff(curses.A_BOLD)

        stdscr.addstr(row, 21, '|')
        stdscr.addstr(row, 23, 'Order:', curses.A_DIM)

        if self._reverse:
            stdscr.attron(curses.A_BOLD)
        stdscr.addstr(row, 30, '[r]everse')
        stdscr.attroff(curses.A_BOLD)


async def render(stdscr: 'curses._CursesWindow', slos: shelve.Shelf) -> None:
    q: 'asyncio.Queue[str]' = asyncio.Queue(maxsize=1)
    asyncio.create_task(tick(q))
    asyncio.create_task(readio(stdscr, q))

    state = State()
    while True:
        k = await q.get()
        if k == 'q':
            return

        state.handle(k)
        items = sorted(slos.values(), key=state.key, reverse=state.reverse)

        height, width = stdscr.getmaxyx()

        i = 0
        stdscr.clear()
        for payload in items:
            if i >= height - 1 - len(payload.results):
                # TODO: pagination
                break

            stdscr.addstr(i, 0, payload.name)
            for result in payload.results:
                stdscr.addstr(i, width // 2, result.name)
                value = f'{result.value:.2f}'
                style = (1 if result.value >= 99.99
                         else 2 if result.value >= 99.9 else 3)
                stdscr.addstr(i, width - len(value) - 1,
                              value, curses.color_pair(style))
                i += 1
            stdscr.addstr(i, 0, '')

        state.render_bar(stdscr, height - 1)
        stdscr.refresh()


def init(stdscr: 'curses._CursesWindow') -> None:
    stdscr.nodelay(True)

    stdscr.idlok(True)
    stdscr.scrollok(True)

    curses.curs_set(0)

    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)


def main(stdscr: 'curses._CursesWindow') -> None:
    init(stdscr)
    stdscr.clear()

    cache_dir = pathlib.Path.home() / '.cache' / 'ddtui'
    os.makedirs(cache_dir, exist_ok=True)
    slos = shelve.open(str(cache_dir / 'slos'))

    try:
        done, _pending = asyncio.run(asyncio.wait([
            poll(slos),
            render(stdscr, slos),
        ], return_when=asyncio.FIRST_COMPLETED))
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
    finally:
        slos.close()
        stdscr.clear()


def cli() -> None:
    curses.wrapper(main)
