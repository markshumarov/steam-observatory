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
    ap.add_argument(
        "--source",
        choices=["base", "demo"],
        default="base",
        help="base — appid базовых игр, demo — appid демо (из demo_map)",
    )
    ap.add_argument("--minutes", type=float, default=25.0, help="сколько минут опрашивать")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--pause", type=float, default=0.0, help="(устарело) пауза между запросами")
    ap.add_argument("--interval", type=float, default=1.1, help="мин. интервал между запросами, сек")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    lineup_path = config.OUT_DIR / "nextfest" / f"{args.slug}_lineup.json"
    lineup = json.loads(lineup_path.read_text(encoding="utf-8"))
    if args.source == "demo":
        map_path = config.OUT_DIR / "nextfest" / f"{args.slug}_demo_map.jsonl"
        demo_ids: set[int] = set()
        for line in map_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("demo_appid"):
                demo_ids.add(int(rec["demo_appid"]))
        appids: list[int] = sorted(demo_ids)
        out_path = config.OUT_DIR / "nextfest" / f"{args.slug}_demo_ccu.jsonl"
    else:
        appids = list(lineup["appids"])
        out_path = config.OUT_DIR / "nextfest" / f"{args.slug}_ccu.jsonl"

    deadline = time.time() + args.minutes * 60
    counter = {"done": 0, "err": 0, "throttled": 0, "last_err": ""}
    lock = threading.Lock()
    rate_lock = threading.Lock()
    last_call = [0.0]

    def rate_limit() -> None:
        """Глобальный лимит: Steam режет частые запросы (429)."""
        with rate_lock:
            wait = args.interval - (time.time() - last_call[0])
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.time()

    def fetch(appid: int) -> None:
        s = _session()
        for attempt in range(1, 4):
            rate_limit()
            try:
                r = s.get(
                    f"{config.STEAM_API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
                    params={"appid": appid},
                    timeout=args.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                with lock:
                    counter["last_err"] = repr(exc)
                continue
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
                            print(
                                f"  опрошено {counter['done']}/{len(appids)} "
                                f"(429: {counter['throttled']}, ошибок: {counter['err']})",
                                flush=True,
                            )
                    return
            if r.status_code == 429:
                with lock:
                    counter["throttled"] += 1
                time.sleep(5 * attempt)
                continue
            with lock:
                counter["last_err"] = f"HTTP {r.status_code}: {r.text[:120]}"
            break
        with lock:
            counter["err"] += 1

    def worker(queue: list[int]) -> None:
        for appid in queue:
            if time.time() > deadline:
                return
            fetch(appid)

    # делим список по потокам
    chunks = [appids[i :: args.workers] for i in range(args.workers)]
    threads = [threading.Thread(target=worker, args=(c,), daemon=True) for c in chunks]
    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(
        f"готово: {counter['done']} ответов, 429: {counter['throttled']}, "
        f"ошибок {counter['err']}, {(time.time() - started) / 60:.1f} мин, файл {out_path}",
        flush=True,
    )
    if counter["last_err"]:
        print("последняя ошибка:", counter["last_err"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
