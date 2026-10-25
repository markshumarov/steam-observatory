"""Проверка: даёт ли снапшот с ?tab=13 другой срез состава фестиваля."""

import re
import sys

import requests

sys.path.insert(0, "src")
from sobs.parse import _unescape_variants  # noqa: E402

PAIR_RE = re.compile(r'"appid"\s*:\s*(\d+)\s*,\s*"demo_appid"\s*:\s*(\d+)')

CASES = [
    ("без вкладки", "https://store.steampowered.com/sale/nextfest", "20211007003741"),
    ("tab=13", "https://store.steampowered.com/sale/nextfest?l=english&tab=13", "20211010070150"),
]

base: set[int] = set()
for name, url, ts in CASES:
    html = requests.get(f"http://web.archive.org/web/{ts}id_/{url}", timeout=90).text
    ids: set[int] = set()
    for _n, text in _unescape_variants(html):
        ids |= {int(a) for a, _b in PAIR_RE.findall(text)}
    extra = ids - base if base else ids
    print(f"{name}: {len(html) // 1024} КБ, appid={len(ids)}, новых={len(extra)}", flush=True)
    base |= ids
print("объединение:", len(base))
