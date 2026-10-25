"""Разведка Gamalytic API: есть ли бесплатный доступ к вишлистам.

Проверяем кандидаты эндпоинтов и смотрим, что отдаётся без ключа.

Запуск: python scripts/probe_gamalytic.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})

APPID = "4534960"  # Dear Passengers — нерелизнутая игра из топ-вишлистов
CANDIDATES = [
    f"https://api.gamalytic.com/game/{APPID}",
    f"https://api.gamalytic.com/steam-games/{APPID}",
    f"https://api.gamalytic.com/steam-games/game/{APPID}",
    "https://api.gamalytic.com/steam-games/list?limit=2",
    "https://api.gamalytic.com/steam-games/upcoming?limit=2",
    "https://api.gamalytic.com/openapi.json",
    "https://api.gamalytic.com/docs",
    "https://gamalytic.com/api/game/4534960",
]

for url in CANDIDATES:
    try:
        r = s.get(url, timeout=25)
        body = r.text[:400].replace("\n", " ")
        print(f"{r.status_code}  {url}\n    {body}\n")
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            try:
                data = r.json()
                keys = list(data.keys()) if isinstance(data, dict) else f"list[{len(data)}]"
                print("    ключи:", keys)
            except json.JSONDecodeError:
                pass
    except Exception as exc:  # noqa: BLE001
        print(f"ERR   {url}\n    {exc!r}\n")
