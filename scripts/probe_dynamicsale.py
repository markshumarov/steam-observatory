"""Проверка эндпоинта полного списка фестиваля.

`store.steampowered.com/actions/ajaxgetdynamicsaleitems` с `max_results=10000`
и `tagids_featured=<id>` — этот запрос делает сама страница Next Fest.

Запуск: python scripts/probe_dynamicsale.py [tagids_featured]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402

TAGID = sys.argv[1] if len(sys.argv) > 1 else "1458863"
URL = "https://store.steampowered.com/actions/ajaxgetdynamicsaleitems"

s = requests.Session()
s.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": config.NEXTFEST_PAGE,
        "X-Requested-With": "XMLHttpRequest",
    }
)
warm = s.get(config.NEXTFEST_PAGE, timeout=90)
print("прогрев:", warm.status_code, len(warm.content))

params = {
    "origin": "https://store.steampowered.com",
    "max_results": "10000",
    "cc": "us",
    "tagids_featured": TAGID,
}
r = s.get(URL, params=params, timeout=120)
print("статус:", r.status_code, "| тип:", r.headers.get("content-type"), "| байт:", len(r.content))

try:
    data = r.json()
except Exception as exc:  # noqa: BLE001
    print("не JSON:", exc, r.text[:300])
    raise SystemExit(1)

print("ключи верхнего уровня:", list(data.keys()))
for key, val in data.items():
    if isinstance(val, list):
        print(f"  {key}: список из {len(val)}")
        if val:
            print("   пример:", json.dumps(val[0], ensure_ascii=False)[:400])
    elif isinstance(val, dict):
        print(f"  {key}: объект с ключами {list(val.keys())[:10]}")
    else:
        print(f"  {key}: {val!r}")

out = config.OUT_DIR / f"dynamicsale_{TAGID}.json"
out.write_text(json.dumps(data, ensure_ascii=False)[:5_000_000], encoding="utf-8")
print("сохранено:", out)
