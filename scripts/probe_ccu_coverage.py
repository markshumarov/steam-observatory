"""Покрытие опроса CCU: сколько демо реально попало в замеры и как распределены проходы."""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEXTFEST = ROOT / "data" / "processed" / "nextfest"
CCU = NEXTFEST / "oct2026_demo_ccu.jsonl"
MAP = NEXTFEST / "oct2026_demo_map.jsonl"

demos = set()
for line in MAP.read_text(encoding="utf-8").splitlines():
    if line.strip():
        rec = json.loads(line)
        if rec.get("demo_appid"):
            demos.add(int(rec["demo_appid"]))

counts: collections.Counter[int] = collections.Counter()
passes = collections.Counter()
for line in CCU.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    counts[int(rec["appid"])] += 1
    passes[rec.get("pass")] += 1

print(f"демо в карте: {len(demos)}")
print(f"демо с замерами: {len(counts)}; без замеров: {len(demos - set(counts))}")
print(f"всего строк: {sum(counts.values())}")
if counts:
    vals = sorted(counts.values())
    print(f"замеров на демо: min={vals[0]}, медиана={vals[len(vals) // 2]}, max={vals[-1]}")
print("строк по проходам:", dict(sorted(passes.items(), key=lambda kv: (kv[0] is None, kv[0]))))
