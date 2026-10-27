"""Оценка прироста вишлистов за фестиваль по прыжкам в топе вишлистов.

Логика: страница фестиваля показывает для каждой игры место в топе вишлистов
сейчас (#N), прыжок за фестиваль (▲k) и текущую оценку вишлистов (≈733K).
Зная, какое место было до фестиваля (N + k), можно по кривой «место → вишлисты»,
построенной по этой же таблице, оценить, сколько вишлистов было тогда, и вычесть.

Оценка грубая: кривая взята из текущего снимка, а оценки вишлистов у PlayRecon
имеют погрешность ±20–30%. Поэтому в отчёте — медиана и квартили, а не точные числа.

Вход:  data/cache/playrecon_fest_table.jsonl
Выход: data/cache/wishlist_gains.json, data/cache/wishlist_gains.md

Запуск: python scripts/playrecon_wishlist_gain.py
"""

from __future__ import annotations

import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
TABLE = CACHE / "playrecon_fest_table.jsonl"
OUT_JSON = CACHE / "wishlist_gains.json"
OUT_MD = CACHE / "wishlist_gains.md"

WL_RE = re.compile(
    r"#([\d\s,]+)"                       # место в топе вишлистов
    r"(?:([\u25b2\u25bc])\s*([\d\s,]+))?"  # прыжок за фестиваль (▲/▼)
    r"\s*\u2248\s*([\d.,]+)\s*([KM]?)"     # оценка: 9,503 / 53,800 / 29K / 1.2M
)


def num(text: str) -> int | None:
    try:
        return int(text.replace(",", "").replace("\u00a0", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_wishlists(cell: str) -> dict | None:
    m = WL_RE.search(cell or "")
    if not m:
        return None
    rank = num(m.group(1))
    arrow, jump, raw_est, suffix = m.group(2), num(m.group(3)), m.group(4), m.group(5) or ""
    # запятая — разделитель тысяч, поэтому её надо убрать до преобразования
    est_value = float(raw_est.replace(",", ""))
    mult = {"K": 1_000, "M": 1_000_000}.get(suffix, 1)
    return {
        "wl_rank": rank,
        "wl_jump": (jump or 0) * (1 if arrow == "\u25b2" else -1) if arrow else 0,
        "wl_est": int(est_value * mult),
    }



def load_rows() -> list[dict]:
    rows = []
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cells = json.loads(line)
        if len(cells) < 8:
            continue
        wl = parse_wishlists(cells[7])
        if not wl:
            continue
        name = re.split(r"(?<=[a-z\)\]0-9])(?=[A-Z])", cells[1], maxsplit=1)[0]
        rows.append(
            {
                "rank": num(cells[0]),
                "name": name,
                "players_24h": num(cells[2]),
                "now": num(cells[3]),
                "peak": num(cells[6]),
                **wl,
            }
        )
    return rows


def curve(rows: list[dict]):
    """Кривая «место в топе вишлистов → оценка вишлистов» (лог-лог, кусочно-линейно)."""
    pts = sorted((r["wl_rank"], r["wl_est"]) for r in rows if r["wl_rank"] and r["wl_est"])
    ranks = [p[0] for p in pts]
    values = [p[1] for p in pts]

    def at(rank: float) -> float | None:
        if not ranks:
            return None
        if rank <= ranks[0]:
            return float(values[0])
        if rank >= ranks[-1]:
            return float(values[-1])
        lo, hi = 0, len(ranks) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ranks[mid] <= rank:
                lo = mid
            else:
                hi = mid
        x0, x1, y0, y1 = ranks[lo], ranks[hi], values[lo], values[hi]
        if x1 == x0:
            return float(y0)
        t = (rank - x0) / (x1 - x0)
        # в лог-лог пространстве кривая почти линейна — интерполируем так
        import math

        return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))

    return at, pts


def main() -> int:
    rows = load_rows()
    at, pts = curve(rows)
    print(f"строк с вишлистами: {len(rows)}, точек кривой: {len(pts)}")

    gains = []
    for r in rows:
        if not r["wl_jump"] or not r["wl_rank"]:
            continue
        rank_before = r["wl_rank"] + r["wl_jump"]  # было хуже, значит место больше
        before = at(rank_before)
        if before is None:
            continue
        gain = r["wl_est"] - before
        gains.append({**r, "wl_rank_before": rank_before, "wl_est_before": int(before),
                      "gain": int(gain)})

    gains.sort(key=lambda r: -r["gain"])
    values = [g["gain"] for g in gains if g["gain"] > 0]
    total = sum(values)

    # связан ли прирост вишлистов с игроками в демо
    pairs = [(g["gain"], g["peak"]) for g in gains if g["gain"] > 0 and g["peak"]]
    corr = None
    if len(pairs) > 20:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx, my = st.mean(xs), st.mean(ys)
        cov = sum((x - mx) * (y - my) for x, y in pairs)
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        corr = round(cov / den, 3) if den else None

    top_gainers = sorted(gains, key=lambda g: -g["gain"])[:25]
    quiet = [g for g in top_gainers if (g["peak"] or 0) < 1000]

    report = {
        "rows_with_wishlists": len(rows),
        "rows_with_jump": len(gains),
        "median_gain": int(st.median(values)) if values else None,
        "p25": sorted(values)[len(values) // 4] if values else None,
        "p75": sorted(values)[3 * len(values) // 4] if values else None,
        "total_gain_top1000": total,
        "corr_gain_vs_players": corr,
        "top25_quiet": len(quiet),
        "over_10k": sum(1 for v in values if v >= 10_000),
        "over_50k": sum(1 for v in values if v >= 50_000),
        "top": gains[:25],
        "notes": [
            "прирост = текущая оценка минус оценка на месте до фестиваля (по кривой из этой же таблицы)",
            "оценки вишлистов PlayRecon — модельные, погрешность ±20–30%",
            "место в топе вишлистов относительное: пока одни растут, другие смещаются вниз",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    md = ["# Прирост вишлистов за фестиваль (оценка)", ""]
    md.append(f"Строк с вишлистами: {len(rows)}; с прыжком в топе: {len(gains)}")
    if values:
        md.append(f"Медианный прирост: **{int(st.median(values)):,}**; "
                  f"квартили {report['p25']:,} – {report['p75']:,}; "
                  f"суммарно по таблице ≈ **{total:,}**".replace(",", " "))
    md.append("")
    md.append(f"Прирост ≥10 000 вишлистов: {report['over_10k']} игр; ≥50 000: {report['over_50k']} игр.")
    md.append(f"Корреляция «прирост вишлистов ↔ пик игроков в демо»: **{corr}** "
              f"(n={len(pairs)}). Из 25 крупнейших приростов у {len(quiet)} игр пик демо ниже 1 000 игроков.")
    md.append("")
    md.append("| Игра | Место в вишлистах | Прыжок | Вишлистов сейчас | Оценка прироста | Пик игроков |")
    md.append("|---|---|---|---|---|---|")
    for g in gains[:25]:
        md.append(f"| {g['name'][:38]} | #{g['wl_rank']} | ▲{g['wl_jump']} | {g['wl_est']:,} | "
                  f"≈{g['gain']:,} | {g['peak']:,} |".replace(",", " "))
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"отчёт: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
