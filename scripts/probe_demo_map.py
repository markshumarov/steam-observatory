"""Как связать игру с её демо (для опроса CCU).

1. Какие типы элементов в ответе lineup (game/demo/...)?
2. Есть ли в живой странице мэппинг demo_appid?
3. Отдаёт ли appdetails поле с демо?

Запуск: python scripts/probe_demo_map.py
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.sources import steam  # noqa: E402

lineup_path = config.OUT_DIR / "dynamicsale_1458863.json"
if lineup_path.exists():
    data = json.loads(lineup_path.read_text(encoding="utf-8"))
    types = collections.Counter(c.get("type") for c in data.get("rgCapsules", []))
    print("типы элементов lineup:", dict(types))
    print("примеры:", data.get("rgCapsules", [])[:3])

# живая страница
live = None
for f in sorted(config.CACHE_DIR.glob("*"), key=lambda p: -p.stat().st_size):
    if f.stat().st_size < 2_000_000:
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    if "sale_nextfest_october_2026" in text:
        live = text
        break

if live:
    for kw in ("demo_appid", "demo_package_id", '"demos"', "demo_id"):
        print(f"живая страница: {kw!r} -> {live.count(kw)}")
    m = re.search(r".{160}demo_appid.{200}", live, re.S)
    if m:
        print("контекст:", repr(m.group(0))[:400])
else:
    print("живая страница не найдена в кэше")

# appdetails: есть ли поле демо
lineup = json.loads((config.OUT_DIR / "nextfest" / "oct2026_lineup.json").read_text(encoding="utf-8"))
sample = lineup["appids"][:3]
det = steam.appdetails(sample, filters=None)
for appid, payload in det.items():
    d = (payload or {}).get("data") or {}
    print(f"appdetails {appid}: ключи с demo -> {[k for k in d if 'demo' in k.lower()]}")
    print("   release_date:", d.get("release_date"), "| type:", d.get("type"), "| name:", d.get("name"))
