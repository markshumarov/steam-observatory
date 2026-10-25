"""Опрос игроков онлайн (CCU) по составу фестиваля — в фоне, до конца фестиваля.

Каждый проход добавляет строки в `data/processed/nextfest/<slug>_ccu.jsonl`:
    {"ts": "...", "appid": 123, "players": 45}

Запуск: python scripts/poll_ccu.py --slug oct2026 --minutes 25 --workers 3
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402
from sobs.sources.steam import UA  # noqa: E402

_lock = threading.Lock()
_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": UA})
        _local.s = s
    return _local.s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="oct2026")
    ap.add_argument("--minutes", type=float, default=25.0, help="сколько минут опрашивать")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--pause", type=float, default=0.5, help="пауза между запросами в потоке")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    lineup_path = config.OUT_DIR / "nextfest" / f"{args.slug}_lineup.json"
    lineup = json.loads(lineup_path.read_text(encoding="utf-8"))
    appids: list[int] = lineup["appids"]
    out_path = config.OUT_DIR / "nextfest" / f"{args.slug}_ccu.jsonl"

    deadline = time.time() + args.minutes * 60
    counter = {"done": 0, "err": 0}
    lock = threading.Lock()

    def fetch(appid: int) -> None:
        s = _session()
        try:
            r = s.get(
                f"{config.STEAM_API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
                params={"appid": appid},
                timeout=args.timeout,
            )
            if r.status_code == 200:
                payload = r.json().get("response", {})
                if payload.get("result") == 1:
                    line = {
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "appid": appid,
                        "players": int(payload.get("player_count", 0)),
                    }
                    with _lock:
                        with out_path.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                    with lock:
                        counter["done"] += 1
                        if counter["done"] % 200 == 0:
                            print(f"  опрошено {counter['done']}/{len(appids)}", flush=True)
                    return
            with lock:
                counter["err"] += 1
        except Exception:  # noqa: BLE001
            with lock:
                counter["err"] += 1
        time.sleep(args.pause)

    def worker(queue: list[int]) -> None:
        for appid in queue:
            if time.time() > deadline:
                return
            fetch(appid)
            time.sleep(args.pause)

    # делим список по потокам
    chunks = [appids[i :: args.workers] for i in range(args.workers)]
    threads = [threading.Thread(target=worker, args=(c,), daemon=True) for c in chunks]
    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(
        f"готово: {counter['done']} ответов, ошибок {counter['err']}, "
        f"{(time.time() - started) / 60:.1f} мин, файл {out_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
