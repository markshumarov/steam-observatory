"""Глубокая разведка бесплатного эндпоинта Gamalytic.

`/steam-games/list` работает без ключа. Выясняем: какие поля есть у записи,
есть ли вишлисты/фолловеры и как фильтровать по appid.

Запуск: python scripts/probe_gamalytic2.py
"""

from __future__ import annotations

import json
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

VARIANTS: list[dict] = [
    {"limit": 1},
    {"limit": 100},
    {"limit": 1, "unreleased": "true"},
    {"limit": 1, "sort": "wishlist"},
    {"limit": 1, "sort": "-wishlist"},
    {"limit": 1, "steamId": 4534960},
    {"limit": 1, "ids": 4534960},
    {"limit": 1, "appIds": 4534960},
]

for params in VARIANTS:
    try:
        r = s.get(BASE, params=params, timeout=30)
    except Exception as exc:  # noqa: BLE001
        print(f"ERR {params}: {exc!r}")
        continue
    print(f"\n=== {r.status_code} {params}")
    if r.status_code != 200:
        print("   ", r.text[:200])
        continue
    try:
        data = r.json()
    except json.JSONDecodeError:
        print("   не JSON:", r.text[:200])
        continue
    result = data.get("result") or []
    print(f"   total={data.get('total')} pages={data.get('pages')} получено={len(result)}")
    if result:
        rec = result[0]
        print("   ключи:", sorted(rec.keys()))
        print("   запись:", json.dumps(rec, ensure_ascii=False)[:900])
        wish_fields = {k: v for k, v in rec.items() if any(t in k.lower() for t in ("wish", "follow", "owner"))}
        print("   поля про вишлисты/фолловеров:", wish_fields or "нет")
