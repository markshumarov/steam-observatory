"""Выборка демо фестиваля, которых НЕТ в борде PlayRecon (топ-1000 по игрокам).

Борд снят из публичного HTML (?top=1000), состав фестиваля — из нашего датасета.
Задача: получить случайную выборку «остальных» демо, чтобы измерить их прирост
вишлистов через MCP (get_app_demand) и не судить обо всём фестивале по верхушке.

Запуск: python scripts/sample_outside_board.py [--n 300] [--seed 20261027]
Выход:  data/cache/sample_outside_board.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402

CACHE = config.CACHE_DIR
GAMES = config.OUT_DIR / "nextfest_games.jsonl"
FEST = "oct2026"

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--seed", type=int, default=20261027)
args = ap.parse_args()

# 1. appid игр из борда: они в RSC-payload сырого HTML (?top=1000)
html = (CACHE / "playrecon_fest.html").read_text(encoding="utf-8", errors="replace")
board_ids = {int(m) for m in re.findall(r"appid\\?\":\s*(\d+)", html)}
print(f"appid в борде (сырой HTML): {len(board_ids)}")

# 2. состав фестиваля
rows = []
for line in GAMES.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    if rec.get("fest") != FEST:
        continue
    appid = rec.get("appid")
    if isinstance(appid, int):
        rows.append(rec)
print(f"демо в составе {FEST}: {len(rows)}")

outside = [r for r in rows if r["appid"] not in board_ids]
print(f"вне борда: {len(outside)}")

random.seed(args.seed)
sample = random.sample(outside, min(args.n, len(outside)))
payload = {
    "fest": FEST,
    "seed": args.seed,
    "board_ids": len(board_ids),
    "lineup": len(rows),
    "outside": len(outside),
    "n": len(sample),
    "games": [
        {
            "appid": r["appid"],
            "demo": r.get("demo_appid") or r.get("demo"),
            "name": r.get("name"),
            "peak": r.get("peak_ccu") or r.get("peak"),
        }
        for r in sample
    ],
}
out = CACHE / "sample_outside_board.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"выборка: {len(sample)} -> {out}")
for g in payload["games"][:5]:
    print("  ", g["appid"], (g["name"] or "")[:50])
