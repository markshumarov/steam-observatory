"""Проверка аномалии «Diamond больше Gold»: тонкая гистограмма приростов.

Если распределение убывает плавно, то тир Diamond (10 000+ без верхней границы)
может законно содержать больше игр, чем узкий Gold (7 000–9 999). Проверяем,
нет ли вместо плавности скачка на границе 10 000 — он означал бы артефакт оценки.

Запуск: python scripts/check_tier_anomaly.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
OUT = CACHE / "tier_anomaly.txt"

data = json.loads((CACHE / "wishlist_gains.json").read_text(encoding="utf-8"))
allg = data.get("all") or []

lines: list[str] = [f"игр с приростом: {len(allg)}"]

# тонкая гистограмма: по 1 000 до 20 000, дальше крупнее
edges = list(range(0, 21_000, 1_000)) + [25_000, 30_000, 40_000, 60_000, 100_000, 10**9]
lines.append("")
lines.append("прирост, диапазон | игр | накопленно")
buckets = []
for lo, hi in zip(edges, edges[1:]):
    n = sum(1 for g in allg if lo <= g["gain"] < hi)
    buckets.append((lo, hi, n))
cum = 0
for lo, hi, n in buckets:
    cum += n
    label = f"{lo:,}–{hi:,}" if hi < 10**9 else f"{lo:,}+"
    lines.append(f"{label:>20} | {n:>4} | {cum:>4}")

lines.append("")
lines.append("проверка «прирост не больше общего числа вишлистов»:")
over = [g for g in allg if g["gain"] > g["wl_est"]]
lines.append(f"  прирост > текущей оценки: {len(over)} (невозможно, значит ошибка)")
neg_before = [g for g in allg if (g.get("wl_est_before") or 0) <= 0]
lines.append(f"  оценка «до» ≤ 0: {len(neg_before)}")
big_ratio = [g for g in allg if g.get("wl_est_before") and g["gain"] / g["wl_est_before"] > 1.5]
lines.append(f"  прирост больше оценки «до» в 1.5+ раза: {len(big_ratio)}")
for g in big_ratio[:8]:
    lines.append(f"    {g['name'][:40]:40} прирост {g['gain']:>8} было {g['wl_est_before']:>8} "
                 f"стало {g['wl_est']:>8} (#{g['wl_rank']}▲{g['wl_jump']})")

# сколько раз оценка «до» упиралась в границу кривой (минимум/максимум)
before_ranks = [g["wl_rank_before"] for g in allg if g.get("wl_rank_before")]
if before_ranks:
    lines.append("")
    lines.append(f"место «до»: минимум {min(before_ranks)}, максимум {max(before_ranks)}")
    lines.append(f"игр, у которых место «до» дальше 5 000: "
                 f"{sum(1 for r in before_ranks if r > 5000)}")

# --- сверка с данными разработчиков (HTMAG, опрос Feb 2026, n≈170) ---
lines.append("")
lines.append("наши перцентили прироста (top-1000 по игрокам, Oct 2026):")
vals = sorted(g["gain"] for g in allg if g["gain"] > 0)


def pct(p: float) -> int:
    if not vals:
        return 0
    idx = min(len(vals) - 1, max(0, int(round(p / 100 * (len(vals) - 1)))))
    return vals[idx]


for p in (30, 50, 70, 90, 95):
    lines.append(f"  p{p}: {pct(p):,}")

lines.append("")
lines.append("HTMAG, опрос разработчиков (вишлисты за фест):")
htmag = {
    "Jun 2024": (384, 884, 2365, 30802, 69040),
    "Oct 2024": (420, 916, 1741, 7800, 18349),
    "Feb 2025": (584, 1079, 2298, 10879, 45655),
    "Feb 2026": (382, 806, 1839, 13461, 57074),
}
for ed, (p30, p50, p70, p95, mx) in htmag.items():
    lines.append(f"  {ed}: p30 {p30:,} / медиана {p50:,} / p70 {p70:,} / p95 {p95:,} / максимум {mx:,}")

# сколько Diamond и Gold должно быть в выборке HTMAG при лог-равномерном
# распределении между p70 и p95 (грубая оценка, но порядок величины виден)
import math  # noqa: E402

n = 170
lo, hi = math.log(1839), math.log(13461)
band = 0.25 * n
gold = band * (math.log(9999) - math.log(7000)) / (hi - lo)
diamond_band = band * (hi - math.log(10000)) / (hi - lo)
diamond = diamond_band + 0.05 * n
lines.append("")
lines.append(f"оценка по перцентилям HTMAG (Feb 2026, n={n}, лог-равномерно p70–p95):")
lines.append(f"  Diamond (10 000+): ~{diamond:.0f} игр, Gold (7 000–9 999): ~{gold:.0f} игр, "
             f"отношение ~{diamond / gold:.1f}x")
lines.append(f"наше отношение Diamond/Gold: {data['tiers'][0]['games'] / data['tiers'][1]['games']:.1f}x")

# доля прироста от текущего числа вишлистов — сколько «съел» фест
shares = sorted(g["gain"] / g["wl_est"] for g in allg if g.get("wl_est") and g["gain"] > 0)
lines.append("")
lines.append("доля прироста от текущего числа вишлистов:")
for p in (10, 30, 50, 70, 90):
    idx = min(len(shares) - 1, max(0, int(round(p / 100 * (len(shares) - 1)))))
    lines.append(f"  p{p}: {shares[idx] * 100:.0f}%")
lines.append(f"  максимум: {shares[-1] * 100:.0f}%")
over_half = sum(1 for s in shares if s > 0.5)
lines.append(f"  игр, где фест дал больше половины всех вишлистов: {over_half} "
             f"({over_half / len(shares) * 100:.1f}%)")


OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {OUT}")


