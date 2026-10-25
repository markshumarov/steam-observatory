"""Забрать бесплатный каталог Gamalytic (теги, жанры, цена, отзывы).

Эндпоинт `/steam-games/list` не требует ключа и отдаёт по 100 записей.
Вишлистов в нём НЕТ (они только в платном `/game/<appid>`), зато есть теги —
их не хватало для изданий 2024+ (там мы знаем только агрегаты по тегам).

Запуск:
    python scripts/ingest_gamalytic.py --probe          # как работает пагинация
    python scripts/ingest_gamalytic.py --fetch --minutes 60
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402

BASE = "https://api.gamalytic.com/steam-games/list"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
OUT = config.OUT_DIR / "gamalytic_games.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})

    if args.probe:
        first = s.get(BASE, params={"limit": 5}, timeout=30).json()
        print("limit=5  ->", [r["steamId"] for r in first["result"]], "| next:", first.get("next"))
        for params in ({"limit": 5, "page": 2}, {"limit": 5, "offset": 5}, {"limit": 5, "page": 1}):
            r = s.get(BASE, params=params, timeout=30).json()
            print(f"{params} ->", [x["steamId"] for x in r["result"]], "| next:", r.get("next"))
        return 0

    if not args.fetch:
        print("укажите --probe или --fetch")
        return 1

    deadline = time.time() + args.minutes * 60
    page = 1
    written = 0
    with OUT.open("a", encoding="utf-8") as fh:
        while time.time() < deadline:
            try:
                data = s.get(BASE, params={"limit": args.limit, "page": page}, timeout=40).json()
            except Exception as exc:  # noqa: BLE001
                print(f"ошибка на странице {page}: {exc!r}", flush=True)
                time.sleep(5)
                continue
            result = data.get("result") or []
            if not result:
                print("пустая страница, стоп", flush=True)
                break
            for rec in result:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            written += len(result)
            if page % 20 == 0:
                print(f"страница {page}: всего {written} записей", flush=True)
            page += 1
            time.sleep(args.pause)

    print(f"готово: {written} записей, файл {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
