"""Проверка стабильности выдачи Gamalytic: сортировка и фильтры по appid."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

BASE = "https://api.gamalytic.com/steam-games/list"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept": "application/json"})


def first_ids(params: dict, n: int = 3) -> list:
    try:
        data = s.get(BASE, params=params, timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        return [f"ERR {exc!r}"]
    return [r.get("steamId") for r in (data.get("result") or [])[:n]]


print("== стабильность без параметров (два вызова подряд)")
print("   ", first_ids({"limit": 3}), first_ids({"limit": 3}))

print("== варианты сортировки (два вызова каждый)")
for sort in ("id", "steamId", "appid", "name", "releaseDate", "copiesSold"):
    a = first_ids({"limit": 3, "sort": sort})
    b = first_ids({"limit": 3, "sort": sort})
    print(f"   sort={sort:12} {'стабильно' if a == b else 'МЕНЯЕТСЯ'}  {a} {b}")

print("== фильтры по конкретной игре (4534960 = Dear Passengers)")
for key in ("steamId", "steamIds", "appid", "appId", "ids", "q", "name", "search"):
    ids = first_ids({"limit": 3, key: 4534960 if key != "q" and key != "name" and key != "search" else "Dear Passengers"})
    hit = "ЕСТЬ" if 4534960 in ids else ""
    print(f"   {key:10} -> {ids} {hit}")
