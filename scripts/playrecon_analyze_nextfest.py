"""Разбор кэшированного ответа nextfest_live: что даёт PlayRecon по фестивалю.

Отчёт пишется в data/cache/pr_nextfest_analysis.txt (UTF-8): консоль Windows
не умеет печатать такие строки, а PowerShell портит трассировки.
"""

from __future__ import annotations

import json
import statistics as st
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / (
    sys.argv[1] if len(sys.argv) > 1 else "playrecon_nextfest_live.json"
)
OUT = ROOT / "data" / "cache" / "pr_nextfest_analysis.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(str(text))


try:
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    payload = (raw.get("result") or {}).get("structuredContent") or {}
    data = payload.get("data") or {}
    rows = data.get("rows") or []

    say(f"фестиваль: {json.dumps(data.get('fest'), ensure_ascii=False)}")
    say(f"состав по PlayRecon: {data.get('lineup')} | строк в ответе: {len(rows)}")
    say(f"coverage: {json.dumps(payload.get('coverage'), ensure_ascii=False)[:400]}")
    say(f"warnings: {json.dumps(payload.get('warnings'), ensure_ascii=False)[:400]}")
    if rows:
        say(f"поля строки: {', '.join(rows[0].keys())}")
        say(f"первая: {json.dumps({k: v for k, v in rows[0].items() if k != 'tags'}, ensure_ascii=False)}")
        say(f"последняя: {json.dumps({k: v for k, v in rows[-1].items() if k != 'tags'}, ensure_ascii=False)}")

    for field in ("peak", "now", "p24", "p24h6", "p24h24", "wlEst", "wlWeek", "wlBefore"):
        vals = sorted(int(r[field]) for r in rows if isinstance(r.get(field), (int, float)))
        if not vals:
            continue
        n = len(vals)
        total = sum(vals)
        top10 = sum(vals[-10:])
        say(
            f"{field:9} n={n:4} min={vals[0]:>7} median={int(st.median(vals)):>7} "
            f"p90={vals[int(n * 0.9)]:>7} max={vals[-1]:>7} сумма={total:>9} "
            f"доля топ-10={100 * top10 / total:5.1f}%"
        )

    pairs = [(int(r["wlEst"]), int(r["peak"])) for r in rows if r.get("wlEst") and r.get("peak")]
    if len(pairs) > 10:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx, my = st.mean(xs), st.mean(ys)
        cov = sum((x - mx) * (y - my) for x, y in pairs)
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        say()
        say(f"пар (вишлисты, пик): {len(pairs)}; корреляция Пирсона = {cov / den:.3f}")
        say(f"медиана отношения пик/вишлисты = {st.median([y / x for x, y in pairs if x > 0]):.4f}")
        say("топ-10 по вишлистам (wlEst, пик, отношение):")
        for wl, pk in sorted(pairs, reverse=True)[:10]:
            say(f"   {wl:>8} {pk:>7} {pk / wl:.4f}")
except Exception:  # noqa: BLE001 — отчёт нужен даже при ошибке
    lines.append(traceback.format_exc())

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {OUT} ({OUT.stat().st_size} байт)")

