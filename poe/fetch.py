import collections

import requests


# https://pathofexile.gamepedia.com/Special:CargoTables
API = "https://pathofexile.gamepedia.com/api.php?action=cargoquery"


def bonus(d: dict) -> float:
    em = 0
    iiq = 0
    iir = 0
    ps = 0
    for stat in d['title']['stat text raw'].split('&lt;br&gt;'):
        if 'increased Rarity of Items' in stat:
            iir = int(stat.split()[0][:-1])
        elif 'increased Quantity of Items' in stat:
            iiq = int(stat.split()[0][:-1])
        elif 'Monster pack size' in stat:
            ps = int(stat.split()[0][1:-1])
        elif 'more Rare Monsters' in stat:
            low, high = stat.split()[0][1:-2].split('-')
            em = (int(low) + int(high)) / 2.
    # TODO: add in iir
    return (1 + iiq/100.) * (1 + ps/100.) * (1 + em/100.)


# low, mid, top
def get_map_values():
    mods = collections.defaultdict(dict)
    for tag in {'default', 'low', 'mid', 'top'}:
        req_tag = f'{tag}_tier_map' if tag != 'default' else tag
        for generation in {1, 2}:
            resp = requests.get(
                f'{API}&tables=mods,spawn_weights'
                '&join_on=mods._pageID=spawn_weights._pageID'
                '&fields=mods.name,mods.stat_text_raw,spawn_weights.weight'
                '&where=mods.domain=5'
                f'%20AND%20mods.generation_type={generation}'
                '%20AND%20mods.name!=%22%22'
                f'%20AND%20spawn_weights.tag=%22{req_tag}%22'
                '%20AND%20spawn_weights.weight%3E0&format=json')
            resp.raise_for_status()
            mods[tag][generation] = [
                (bonus(x), int(x['title']['weight']))
                for x in resp.json()['cargoquery']]

    for tier in {'low', 'mid', 'top'}:
        prefixes = mods[tier][1] + mods['default'][1]
        suffixes = mods[tier][2] + mods['default'][2]

        prefix = sum(x[0] * x[1] for x in prefixes) / sum(x[1] for x in prefixes)
        suffix = sum(x[0] * x[1] for x in suffixes) / sum(x[1] for x in suffixes)

        # TODO: verify distribution of number of prefixes and suffixes
        value = ((prefix + suffix) / 2.) ** 1#4.5
        print(tier, value)


get_map_values()
