"""Полный справочник тегов Steam: tagid -> название.

Два источника, оба публичные:
1. `tagdata/populartags/english` — список популярных тегов (~430);
2. страницы игр магазина — в них лежат пары `"tagid": N, "name": "..."`,
   это добирает нишевые теги, которых нет в первом списке.

Справочник дополняется, уже известные названия не затираются.

Запуск:
    python scripts/fetch_tag_names.py             # до 40 страниц игр
    python scripts/fetch_tag_names.py --pages 0   # только tagdata
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.http import get_json  # noqa: E402

NEXTFEST = config.OUT_DIR / "nextfest"
TAGS_FILE = NEXTFEST / "steam_tags.json"
GAMES_FILE = config.OUT_DIR / "nextfest_games.jsonl"
SOURCE = "https://store.steampowered.com/tagdata/populartags/english"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
PAIR_RE = re.compile(r'"tagid"\s*:\s*(\d+)\s*,\s*"name"\s*:\s*"([^"]+)"')


def load_existing() -> dict[int, str]:
    out: dict[int, str] = {}
    if TAGS_FILE.exists():
        for item in json.loads(TAGS_FILE.read_text(encoding="utf-8")):
            if isinstance(item, dict) and item.get("tagid"):
                out[int(item["tagid"])] = item.get("name") or ""
    return out


def missing_ids(known: dict[int, str]) -> set[int]:
    """Какие теги встречаются в данных, но без названия."""
    need: set[int] = set()
    for path in (config.OUT_DIR / "nextfest_tag_facets.jsonl",):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if not known.get(int(rec["tagid"])):
                    need.add(int(rec["tagid"]))
    return need


def sample_appids(limit: int) -> list[int]:
    """Разные игры из датасета: по одной на каждые N строк, чтобы теги не повторялись."""
    if not GAMES_FILE.exists():
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for line in GAMES_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        appid = int(json.loads(line)["appid"])
        if appid not in seen:
            seen.add(appid)
            ids.append(appid)
    step = max(1, len(ids) // max(1, limit))
    return ids[::step][:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=40, help="сколько страниц игр открыть")
    args = ap.parse_args()

    known = load_existing()
    before = len(known)

    for item in get_json(SOURCE, suffix=".json") or []:
        tid, name = int(item.get("tagid") or 0), (item.get("name") or "").strip()
        if tid and name and not known.get(tid):
            known[tid] = name

    need = missing_ids(known)
    print(f"справочник: {len(known)} тегов, без названия в данных: {len(need)}", flush=True)

    session = requests.Session()
    session.headers.update(UA)
    fetched = 0
    for appid in sample_appids(args.pages):
        if not need:
            break
        try:
            html = session.get(
                f"https://store.steampowered.com/app/{appid}/?l=english", timeout=45
            ).text
        except requests.RequestException:
            continue
        fetched += 1
        for tid, name in PAIR_RE.findall(html):
            tid = int(tid)
            if tid in need:
                known[tid] = name
                need.discard(tid)
        time.sleep(0.6)

    payload = [{"tagid": t, "name": n} for t, n in sorted(known.items()) if n]
    TAGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"страниц открыто: {fetched}; справочник: {len(payload)} (было {before}); "
          f"осталось без названия: {len(need)}")
    if need:
        print("id без названия:", sorted(need)[:20])
    print("файл:", TAGS_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
