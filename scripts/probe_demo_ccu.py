"""Проверка: как получить demo appid игры и совпадает ли его CCU с трекерами.

Запуск: python scripts/probe_demo_ccu.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402
from sobs.sources.steam import UA, current_players  # noqa: E402

lineup = json.loads((config.OUT_DIR / "nextfest" / "oct2026_lineup.json").read_text(encoding="utf-8"))
appids = lineup["appids"][:4]

s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

DEMO_LINK_RE = re.compile(r'href="[^"]*?/app/(\d+)/[^"]*"[^>]*>\s*(?:Download|Play|Играть|Скачать)[^<]*[Dd]emo')

for appid in appids:
    url = f"{config.STEAM_STORE}/app/{appid}/"
    html = s.get(url, timeout=60).text
    name = re.search(r"<title>(.*?)</title>", html, re.S)
    name = re.sub(r"\s+", " ", name.group(1)).strip() if name else "?"
    print(f"\n=== {appid}  {name}")
    print("   base CCU:", current_players(appid))

    ids = set(re.findall(r'steam://install/(\d+)', html))
    print("   steam://install:", sorted(ids)[:5])
    m = re.search(r".{120}[Dd]emo.{200}", html, re.S)
    print("   контекст demo:", repr(m.group(0))[:420] if m else "нет слова demo")

    # пробуем найти demo appid через поиск по каталогу демо
    r = s.get(
        f"{config.STEAM_STORE}/search/results/",
        params={"json": 1, "category1": 10, "term": re.sub(r"[^A-Za-z0-9 ]", "", name.split(" on Steam")[0])[:60], "cc": "us", "l": "english", "count": 20},
        timeout=60,
    )
    try:
        items = r.json().get("items", [])
    except Exception:  # noqa: BLE001
        items = []
    cand = []
    for it in items[:8]:
        m2 = re.search(r"/apps/(\d+)/", it.get("logo", ""))
        if m2:
            cand.append((int(m2.group(1)), it.get("name")))
    print("   кандидаты-демо из поиска:", cand[:4])
    for demo_id, demo_name in cand[:2]:
        print(f"      demo {demo_id} {demo_name!r} CCU:", current_players(demo_id))
