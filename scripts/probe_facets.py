"""Проверка гипотезы: страницы фестиваля с фасетами/пагинацией содержат список игр.

Запуск: python scripts/probe_facets.py 20230601 20230801
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.parse import extract_games, page_title  # noqa: E402
from sobs.sources import wayback  # noqa: E402

frm = sys.argv[1] if len(sys.argv) > 1 else "20230601"
to = sys.argv[2] if len(sys.argv) > 2 else "20230801"
test_n = int(sys.argv[3]) if len(sys.argv) > 3 else 3

snaps = wayback.cdx(
    config.NEXTFEST_PAGE, from_ts=frm, to_ts=to, limit=400, match_type="prefix"
)
print(f"снапшотов с префиксом: {len(snaps)}")

interesting = [s for s in snaps if ("facets" in s.original or "offset" in s.original or "tab=" in s.original)]
print(f"из них с фасетами/офсетом/табом: {len(interesting)}")
for s in interesting[:10]:
    print(f"   {s.timestamp} {s.length:>8}  {s.original[:130]}")

interesting.sort(key=lambda s: s.length, reverse=True)
for snap in interesting[:test_n]:
    try:
        html = wayback.fetch_snapshot(snap)
    except Exception as exc:  # noqa: BLE001
        print("ERR", snap.original[:80], exc)
        continue
    games, strategy = extract_games(html)
    groups = collections.Counter(tuple(sorted(g.keys()))[:6] for g in games)
    print(f"\n== {snap.original[:120]}")
    print(f"   {len(html)} байт | title={page_title(html)!r}")
    print(f"   объектов: {len(games)} | стратегия: {strategy}")
    for sig, n in groups.most_common(4):
        print(f"      [{n}] {', '.join(sig)}")
    sample = next((g for g in games if g.get("tags")), None)
    print("   пример с тегами:", json.dumps(sample, ensure_ascii=False)[:400] if sample else "нет")
