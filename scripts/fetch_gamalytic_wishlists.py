"""Вишлисты всех игр фестиваля из публичного эндпоинта Gamalytic.

Страница gamalytic.com/game/<appid> тянет данные из
https://gamalytic.com/api/game-details/<appid> — без ключа и без браузера.
Оттуда берём wishlists (текущее число) и topWish (место в топе вишлистов).

Запуск: python scripts/fetch_gamalytic_wishlists.py [--workers 5]
Выход:  data/cache/gamalytic_wishlists.jsonl (докачиваемый)
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
GAMES = ROOT / "data" / "processed" / "nextfest_games.jsonl"
OUT = CACHE / "gamalytic_wishlists.jsonl"
FEST = "oct2026"
URL = "https://gamalytic.com/api/game-details/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

ap = argparse.ArgumentParser()
ap.add_argument("--workers", type=int, default=5)
ap.add_argument("--fest", default=FEST)
args = ap.parse_args()

lock = threading.Lock()
done: set[int] = set()
if OUT.exists():
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            done.add(json.loads(line)["appid"])

appids: list[int] = []
for line in GAMES.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    if rec.get("fest") == args.fest and isinstance(rec.get("appid"), int):
        appids.append(rec["appid"])

todo = [a for a in appids if a not in done]
print(f"игр в составе {args.fest}: {len(appids)}, уже снято: {len(done)}, осталось: {len(todo)}",
      flush=True)

counter = {"n": 0, "hit": 0, "err": 0}
fh = OUT.open("a", encoding="utf-8")
started = time.time()


def fetch(appid: int) -> None:
    row = {"appid": appid, "wishlists": None, "topWish": None, "name": None}
    for attempt in (1, 2):
        try:
            resp = requests.get(URL.format(appid), headers=HEADERS, timeout=45)
            if resp.status_code == 200:
                data = resp.json().get("data") or {}
                row.update(
                    wishlists=data.get("wishlists"),
                    topWish=data.get("topWish"),
                    name=data.get("name"),
                )
                break
            if resp.status_code in (404, 400):
                break
        except Exception:  # noqa: BLE001
            time.sleep(1.0 * attempt)
    with lock:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        counter["n"] += 1
        if row["wishlists"]:
            counter["hit"] += 1
        elif row["wishlists"] is None:
            counter["err"] += 1
        if counter["n"] % 250 == 0:
            fh.flush()
            spent = time.time() - started
            rate = counter["n"] / spent if spent else 0
            left = (len(todo) - counter["n"]) / rate if rate else 0
            print(f"{counter['n']}/{len(todo)} | с вишлистами {counter['hit']} | "
                  f"{rate:.1f} игр/с | осталось ~{left / 60:.1f} мин", flush=True)


with ThreadPoolExecutor(max_workers=args.workers) as pool:
    list(pool.map(fetch, todo))

fh.flush()
fh.close()
print(f"готово: снято {counter['n']}, с вишлистами {counter['hit']}, ошибок {counter['err']}",
      flush=True)
