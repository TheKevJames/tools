import asyncio
import curses
import os
import pathlib
import shelve
import time

import aiohttp


API = 'https://api.datadoghq.com/api/v1'
HEADERS = {
    'Content-Type': 'application/json',
    'DD-API-KEY': os.environ['DD_API_KEY'],
    'DD-APPLICATION-KEY': os.environ['DD_APP_KEY'],
}
PARAMS = {}


def parse(s: str):
    for i, c in enumerate(s):
        if c == '(':
            x = s[i:].find(')')
            rem = s[i+x+1:].strip()
            if rem:
                return (rem[0], parse(s[i+1:i+x]), parse(rem[1:]))
            else:
                return ('=', parse(s[i+1:i+s[i:].find(')')]))
        elif c in {'+', '*'}:
            return (c, parse(s[:i]), parse(s[i+1:]))

    return ('=', s.replace('MASK', '()').strip())


async def visit(s: aiohttp.ClientSession, ast: tuple):
    if ast[0] == '=':
        if isinstance(ast[1], tuple):
            return await visit(s, ast[1])

        resp = await s.get(f'{API}/query', params={**PARAMS, 'query': ast[1]})
        series = (await resp.json())['series']
        if not series:
            return {}
        return dict(series[0]['pointlist'])
    elif ast[0] == '+':
        lhs = await visit(s, ast[1])
        rhs = await visit(s, ast[2])
        return {k: lhs.get(k, 0) + rhs.get(k, 0) for k in set(lhs) | set(rhs)}
    elif ast[0] == '*':
        lhs = await visit(s, ast[1])
        rhs = await visit(s, ast[2])
        return {k: lhs.get(k, 0) * rhs.get(k, 0) for k in set(lhs) | set(rhs)}
    else:
        raise Exception(f'unsupported AST node {ast[0]}')


async def slo(s: aiohttp.ClientSession, slos: shelve.Shelf, data: dict):
    if time.time() - slos[data['id']].get('updated', 0) < 60:
        return

    results = []
    if data['type'] == 'metric':
        queries = data['query']['numerator'].strip()
        ast = parse(queries.replace('()', 'MASK'))
        numerators = await visit(s, ast)

        queries = data['query']['denominator'].strip()
        ast = parse(queries.replace('()', 'MASK'))
        denominators = await visit(s, ast)

        points = {k: numerators[k] / denominators[k]
                  for k in set(numerators) & set(denominators)}
        result = 100. * sum(points.values()) / len(points)
        results.append({'name': data['name'], 'value': result})
    elif data['type'] == 'monitor':
        for monitor in data['monitor_ids']:
            resp = await s.get(f'{API}/monitor/{monitor}')
            payload = await resp.json()

            query, _gt, target_str = payload['query'].rsplit(' ', 2)
            target = float(target_str)
            _agg, query = query.split(':', 1)

            resp = await s.get(f'{API}/query', params={**PARAMS, 'query': query})
            monitors = [(sum((x[1] or 0.) > target for x in series['pointlist'])
                         / len(series['pointlist']))
                        for series in (await resp.json())['series']]
            result = 100 - sum(monitors) / len(monitors)

            results.append({'name': payload['name'], 'value': result})
    else:
        assert False, f'unsupported SLO type {data["type"]}'

    slos[data['id']] = {'name': data['name'],
                        'results': results, 'updated': time.time()}


async def poll(slos: shelve.Shelf):
    async with aiohttp.ClientSession(headers=HEADERS, raise_for_status=True) as s:
        resp = await s.get(f'{API}/slo')
        slos_data = (await resp.json())['data']

        while True:
            PARAMS['to'] = int(time.time()) - 600
            PARAMS['from'] = PARAMS['to'] - 60 * 60 * 24 * 7

            try:
                await asyncio.gather(*[slo(s, slos, data) for data in slos_data])
            except Exception as e:
                try:
                    if e.status == 429:
                        await asyncio.sleep(int(e.headers.get('x-ratelimit-reset')) + 1)
                        continue
                except Exception:
                    pass
                raise e
            else:
                await asyncio.sleep(60 * 60)


async def readio(stdscr, q: asyncio.Queue):
    while True:
        k = stdscr.getch(0, 0)
        if k != -1:
            await q.put(k)
        await asyncio.sleep(1)


async def tick(stdscr, q: asyncio.Queue):
    for _ in range(5):
        await q.put('r')
        await asyncio.sleep(1)

    while True:
        await q.put('r')
        await asyncio.sleep(10)


async def render(stdscr, slos: shelve.Shelf):
    q = asyncio.Queue(maxsize=1)
    asyncio.create_task(tick(stdscr, q))
    asyncio.create_task(readio(stdscr, q))

    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)

    sort_mode = 'name'  # TODO: enum
    while True:
        k = await q.get()
        if k == ord('q'):
            return
        elif k == ord('n'):
            sort_mode = 'name'
        elif k == ord('v'):
            sort_mode = 'value'

        if sort_mode == 'name':
            items = sorted(slos.values(), key=lambda xs: xs['name'])
        elif sort_mode == 'value':
            items = reversed(sorted(slos.values(), key=lambda xs: min(
                x['value'] for x in xs['results'])))

        height, width = stdscr.getmaxyx()

        i = 0
        stdscr.clear()
        for payload in items:
            stdscr.addstr(i, 0, payload['name'])
            for result in payload['results']:
                stdscr.addstr(i, width//2, result['name'])
                value = f'{result["value"]:.2f}'
                style = 1 if result['value'] >= 99.99 else 2 if result['value'] >= 99.9 else 3
                stdscr.addstr(i, width - len(value) - 1,
                              value, curses.color_pair(style))
                i += 1
            stdscr.addstr(i, 0, '')

        stdscr.addstr(height-1, 0, 'Sort:')
        stdscr.addstr(height-1, 6, '[n]ame',
                      curses.A_BOLD if sort_mode == 'name' else 0)
        stdscr.addstr(height-1, 13, '[v]alue',
                      curses.A_BOLD if sort_mode == 'value' else 0)

        stdscr.refresh()


def main(stdscr) -> None:
    stdscr.nodelay(True)
    stdscr.idlok(True)
    stdscr.scrollok(True)
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

        stdscr.clear()
    finally:
        slos.close()


def cli():
    curses.wrapper(main)
