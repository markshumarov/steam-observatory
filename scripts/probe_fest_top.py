"""Есть ли в сыром HTML страницы фестиваля все строки (а не только видимые)?

Страница серверная (RSC), таблица в DOM может виртуализироваться, поэтому
проверяем сырой ответ: сколько appid встречается при разных top=.

Запуск: python scripts/probe_fest_top.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.http import get_text  # noqa: E402

OUT = config.CACHE_DIR / "probe_fest_top.txt"
BASE = "https://app.playrecon.com/fests/nextfest/autumn-2026"

lines: list[str] = []
for top in (1000, 2000, 4000, 8000):
    url = f"{BASE}?top={top}&sort=players&dir=desc"
    try:
        html = get_text(url)
    except Exception as exc:  # noqa: BLE001
        lines.append(f"top={top}: ошибка {exc}")
        continue
    appids = len(re.findall(r'"appid":\d+', html))
    names = len(re.findall(r'"name":"', html))
    rows = len(re.findall(r'"wlRank"', html))
    lines.append(f"top={top}: html={len(html)} appid={appids} name={names} wlRank={rows}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
