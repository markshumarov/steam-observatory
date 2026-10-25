"""Мэппинг «игра -> её демо» по страницам магазина.

CCU демо считается по appid самого демо, а в составе фестиваля указаны appid
базовых игр. Поэтому для каждой игры забираем страницу магазина и достаём
`related_items.demo_appid` (или ссылку steam://install/<demo_appid>).

Результат дописывается построчно в `data/processed/nextfest/<slug>_demo_map.jsonl`
и безопасен к перезапуску (уже обработанные appid пропускаются).

Запуск: python scripts/ingest_demo_map.py --slug oct2026 --minutes 120
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402
from sobs.sources.steam import UA  # noqa: E402

DEMO_APPID_RE = re.compile(r'"demo_appid"\s*:\s*\[(\d+)')
INSTALL_RE = re.compile(r'steam://install/(\d+)')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="oct2026")
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=0.7, help="пауза между запросами, сек")
    args = ap.parse_args()

    base = config.OUT_DIR / "nextfest"
    lineup = json.loads((base / f"{args.slug}_lineup.json").read_text(encoding="utf-8"))
    out_path = base / f"{args.slug}_demo_map.jsonl"

    done: set[int] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(int(json.loads(line)["appid"]))
                except Exception:  # noqa: BLE001
                    pass
    todo = [a for a in lineup["appids"] if a not in done]
    print(f"всего игр: {len(lineup['appids'])}, уже обработано: {len(done)}, осталось: {len(todo)}", flush=True)

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})

    deadline = time.time() + args.minutes * 60
    ok = miss = err = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for i, appid in enumerate(todo, 1):
            if time.time() > deadline:
                print("время вышло", flush=True)
                break
            url = f"{config.STEAM_STORE}/app/{appid}/"
            demo_appid = None
            name = ""
            try:
                html = s.get(url, timeout=45).text
                m = DEMO_APPID_RE.search(html) or INSTALL_RE.search(html)
                demo_appid = int(m.group(1)) if m else None
                t = TITLE_RE.search(html)
                name = re.sub(r"\s+", " ", t.group(1)).strip() if t else ""
                ok += 1 if demo_appid else 0
                miss += 0 if demo_appid else 1
            except Exception as exc:  # noqa: BLE001
                err += 1
                if err % 50 == 1:
                    print(f"  ошибка на {appid}: {exc!r}", flush=True)
            fh.write(
                json.dumps(
                    {
                        "appid": appid,
                        "demo_appid": demo_appid,
                        "name": name,
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fh.flush()
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}: с демо {ok}, без демо {miss}, ошибок {err}", flush=True)
            time.sleep(args.interval)

    print(f"готово: с демо {ok}, без демо {miss}, ошибок {err}; файл {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
