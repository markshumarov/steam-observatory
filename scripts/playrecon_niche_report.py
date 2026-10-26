"""Разбор ответа market_niche в читаемый отчёт."""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cache" / "pr_niche_report.txt"


def load(pattern: str) -> dict:
    files = sorted(glob.glob(str(ROOT / "data" / "cache" / pattern)))
    raw = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    return (raw.get("result") or {}).get("structuredContent") or {}


lines: list[str] = []
for payload in [load("playrecon_market_niche_*.json")]:
    data = payload.get("data") or {}
    lines.append(f"тег: {data.get('tag')} (match={data.get('match')}), в дереве ещё +{data.get('treeWouldAdd')}")
    lines.append(f"выпущено всего: {data.get('released')}, за 12 месяцев: {data.get('releasedLast12m')}, "
                 f"анонсировано: {data.get('announced')}")
    out = data.get("outcomes") or {}
    rev = out.get("reviews") or {}
    lines.append(f"итоги релизов ({out.get('basedOnReleases')} шт., {out.get('window')}):")
    lines.append("   отзывы: p10={p10} p25={p25} медиана={median} p75={p75} p90={p90}".format(**rev))
    lines.append(f"   доля с <10 отзывов: {100 * (out.get('shareUnder10Reviews') or 0):.1f}%")
    lines.append(f"медианная цена: {data.get('medianPrice')}, доля F2P: "
                 f"{100 * (data.get('freeToPlayShare') or 0):.1f}%")
    lines.append("по годам: год | релизов | медиана отзывов | доля <10 отзывов")
    for row in data.get("byYear") or []:
        lines.append(
            f"   {row.get('year')} | {row.get('releases'):>5} | {row.get('medianReviews'):>8} | "
            f"{100 * (row.get('shareUnder10Reviews') or 0):5.1f}% | слишком свежих: {row.get('tooFreshToJudge')}"
        )
    for key, value in (payload.get("coverage") or {}).items():
        lines.append(f"coverage[{key}] = {json.dumps(value, ensure_ascii=False)[:200]}")
    for w in payload.get("warnings") or []:
        lines.append(f"warning: {json.dumps(w, ensure_ascii=False)[:300]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {OUT}")
