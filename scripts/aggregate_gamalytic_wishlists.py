"""Сводка вишлистов Gamalytic по составу фестиваля + сверка с PlayRecon.

Вход:  data/cache/gamalytic_wishlists.jsonl, data/processed/nextfest_games.jsonl,
       site/data/story.json (топ-200 борда с appid и оценкой PlayRecon)
Выход: data/cache/gamalytic_report.json + печать

Запуск: python scripts/aggregate_gamalytic_wishlists.py
"""

from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
SITE = ROOT / "site" / "data"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

rows = []
bad = 0
for line in (CACHE / "gamalytic_wishlists.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        bad += 1
wish = {r["appid"]: r for r in rows}
print(f"снято игр: {len(rows)}, с вишлистами: {sum(1 for r in rows if r.get('wishlists'))}, "
      f"битых строк: {bad}")

values = sorted(r["wishlists"] for r in rows if r.get("wishlists"))
n = len(values)


def q(p: float) -> int:
    return values[min(n - 1, int(p * n))]


def count(lo: int, hi: int | None) -> int:
    return sum(1 for v in values if v >= lo and (hi is None or v < hi))


# бакеты «кто участвовал»: границы — квантили, чтобы шло от большего к меньшему
bounds = [q(0.5), q(0.75), q(0.9), q(0.97)]
buckets = [
    {"key": "b0", "from": 0, "to": bounds[0], "games": count(0, bounds[0])},
    {"key": "b1", "from": bounds[0], "to": bounds[1], "games": count(bounds[0], bounds[1])},
    {"key": "b2", "from": bounds[1], "to": bounds[2], "games": count(bounds[1], bounds[2])},
    {"key": "b3", "from": bounds[2], "to": bounds[3], "games": count(bounds[2], bounds[3])},
    {"key": "b4", "from": bounds[3], "to": None, "games": count(bounds[3], None)},
]
print("бакеты (квантили):", [(b["from"], b["to"], b["games"]) for b in buckets])
print("медиана:", st.median(values), "p90:", q(0.9), "макс:", values[-1])

# пороги бенчмарка Крисса на тех же данных
for lo, hi, label in ((0, 1_000, "до 1 000"), (1_000, 8_000, "1 000–7 999"),
                      (8_000, 50_000, "8 000–49 999"), (50_000, 90_000, "50 000–89 999"),
                      (90_000, None, "90 000+")):
    print(f"  {label}: {count(lo, hi)}")

# сверка с PlayRecon на играх борда
story = json.loads((SITE / "story.json").read_text(encoding="utf-8"))
board = (story.get("attention") or {}).get("games") or []
diffs = []
for g in board:
    gv = (wish.get(g.get("appid")) or {}).get("wishlists")
    pv = g.get("wlEst")
    if gv and pv:
        diffs.append((gv / pv - 1) * 100)
if diffs:
    diffs.sort()
    print(f"сверка с PlayRecon: игр {len(diffs)}, медиана расхождения "
          f"{st.median(diffs):+.1f}%, p10 {diffs[len(diffs) // 10]:+.1f}%, "
          f"p90 {diffs[9 * len(diffs) // 10]:+.1f}%")

report = {
    "games": len(rows),
    "with_wishlists": sum(1 for r in rows if r.get("wishlists")),
    "median": int(st.median(values)),
    "bounds": bounds,
    "buckets": buckets,
    "croscheck": {
        "n": len(diffs),
        "median_pct": round(st.median(diffs), 1) if diffs else None,
        "p10": round(diffs[len(diffs) // 10], 1) if diffs else None,
        "p90": round(diffs[9 * len(diffs) // 10], 1) if diffs else None,
    },
}
(CACHE / "gamalytic_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("отчёт: data/cache/gamalytic_report.json")
