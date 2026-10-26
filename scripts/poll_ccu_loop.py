"""Непрерывный опрос CCU до конца фестиваля.

Каждый проход: загружает список appid (демо или базовые игры), опрашивает все
по очереди, затем **перечитывает список** (мэппинг демо дополняется параллельно
другим скриптом) и идёт на новый проход. Так поллер начинает работать сразу и
постепенно охватывает все игры.

Строки результата: `{"ts", "appid", "players", "pass"}` в
`data/processed/nextfest/<slug>_demo_ccu.jsonl` (или `<slug>_ccu.jsonl`).

Запуск: python scripts/poll_ccu_loop.py --slug oct2026 --source demo --hours 20
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402
from sobs.sources.steam import UA  # noqa: E402

CCU_URL = f"{config.STEAM_API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"


def load_ids(slug: str, source: str) -> list[int]:
    base = config.OUT_DIR / "nextfest"
    if source == "demo":
        path = base / f"{slug}_demo_map.jsonl"
        if not path.exists():
            return []
        ids: set[int] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("demo_appid"):
                ids.add(int(rec["demo_appid"]))
        return sorted(ids)

    lineup = json.loads((base / f"{slug}_lineup.json").read_text(encoding="utf-8"))
    return list(lineup["appids"])


def load_counts(out_path: Path) -> collections.Counter:
    """Сколько замеров уже накоплено по каждому appid."""
    counts: collections.Counter = collections.Counter()
    if not out_path.exists():
        return counts
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        counts[int(rec["appid"])] += 1
    return counts


def order_ids(ids: list[int], out_path: Path) -> list[int]:
    """Порядок обхода: сначала те, у кого меньше замеров.

    Проход по 7 тысячам демо занимает больше двух часов, а смена в CI короче,
    поэтому обход «с начала списка» оставлял бы хвост без замеров навсегда.
    Сортировка по числу уже сделанных замеров выравнивает покрытие: каждый
    следующий проход начинается там, где данных меньше всего.
    """
    counts = load_counts(out_path)
    if not counts:
        return ids
    return sorted(ids, key=lambda a: (counts.get(a, 0), a))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="oct2026")
    ap.add_argument("--source", choices=["demo", "base"], default="demo")
    ap.add_argument("--hours", type=float, default=20.0)
    ap.add_argument("--interval", type=float, default=1.1)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    out_path = config.OUT_DIR / "nextfest" / (
        f"{args.slug}_demo_ccu.jsonl" if args.source == "demo" else f"{args.slug}_ccu.jsonl"
    )
    deadline = time.time() + args.hours * 3600

    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    last_call = 0.0
    started = time.time()
    total = {"ok": 0, "no_stats": 0, "throttled": 0, "err": 0}
    pass_no = 0

    while time.time() < deadline:
        ids = load_ids(args.slug, args.source)
        if not ids:
            print("список пуст, ждём 60 с", flush=True)
            time.sleep(60)
            continue

        pass_no += 1
        ids = order_ids(ids, out_path)
        done = no_stats = throttled = err = 0
        pass_started = time.time()
        print(f"=== проход {pass_no}: {len(ids)} appid", flush=True)

        with out_path.open("a", encoding="utf-8") as fh:
            for i, appid in enumerate(ids, 1):
                if time.time() > deadline:
                    break
                # вежливый глобальный лимит
                wait = args.interval - (time.time() - last_call)
                if wait > 0:
                    time.sleep(wait)
                last_call = time.time()

                try:
                    r = s.get(CCU_URL, params={"appid": appid}, timeout=args.timeout)
                except Exception as exc:  # noqa: BLE001
                    err += 1
                    if err % 50 == 1:
                        print(f"    сеть: {exc!r}", flush=True)
                    continue

                if r.status_code == 200:
                    payload = r.json().get("response", {})
                    if payload.get("result") == 1:
                        fh.write(
                            json.dumps(
                                {
                                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "appid": appid,
                                    "players": int(payload.get("player_count", 0)),
                                    "pass": pass_no,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        fh.flush()
                        done += 1
                    else:
                        no_stats += 1  # result 42 — у приложения нет статистики
                elif r.status_code == 429:
                    throttled += 1
                    time.sleep(5)
                else:
                    err += 1

                if i % 250 == 0:
                    print(
                        f"    {i}/{len(ids)}: ok={done}, без статистики={no_stats}, "
                        f"429={throttled}, ошибок={err}",
                        flush=True,
                    )

        total["ok"] += done
        total["no_stats"] += no_stats
        total["throttled"] += throttled
        total["err"] += err
        print(
            f"--- проход {pass_no} за {(time.time() - pass_started) / 60:.1f} мин: "
            f"ok={done}, без статистики={no_stats}, 429={throttled}, ошибок={err}",
            flush=True,
        )

    print(
        f"остановлено по времени ({(time.time() - started) / 60:.1f} мин): "
        f"проходов={pass_no}, всего ok={total['ok']}, 429={total['throttled']}, "
        f"ошибок={total['err']}; файл {out_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
