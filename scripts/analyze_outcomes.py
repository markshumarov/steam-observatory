"""Что происходит с участником Next Fest: исходы по изданиям и по тегам.

Считаем по нашему датасету (составы фестивалей + обогащение Gamalytic):
  * размер состава и доля «незамеченных» (нет отзывов);
  * доля невышедших игр;
  * медианный тираж по изданиям (с оговоркой про возраст);
  * исходы по тегам: медианный тираж и доля незамеченных там, где хватает данных;
  * динамика доли тега между изданиями (что растёт, что падает).

Вход:  data/processed/nextfest_games.jsonl
Выход: data/processed/analysis_outcomes.json, docs/analysis.md

Запуск: python scripts/analyze_outcomes.py
"""

from __future__ import annotations

import collections
import json
import statistics as st
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import FESTS  # noqa: E402

GAMES = config.OUT_DIR / "nextfest_games.jsonl"
OUT_JSON = config.OUT_DIR / "analysis_outcomes.json"
OUT_MD = config.ROOT / "docs" / "analysis.md"

NOW = time.time() * 1000  # мс
MONTH = 30.44 * 24 * 3600 * 1000


def load() -> dict[str, list[dict]]:
    by_fest: dict[str, list[dict]] = collections.defaultdict(list)
    for line in GAMES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            by_fest[rec["fest"]].append(rec)
    return by_fest


def q(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(len(values) * p)))
    return values[idx]


def edition_stats(rows: list[dict]) -> dict:
    n = len(rows)
    copies = [r["copies_sold"] for r in rows if isinstance(r.get("copies_sold"), (int, float))]
    scores = [r["review_score"] for r in rows if isinstance(r.get("review_score"), (int, float))]
    unreleased = sum(1 for r in rows if r.get("unreleased"))
    no_score = sum(1 for r in rows if r.get("review_score") is None)
    low = sum(1 for r in rows if isinstance(r.get("review_score"), (int, float)) and r["review_score"] < 70)
    ages = [
        (NOW - r["release_ts"]) / MONTH
        for r in rows
        if r.get("release_ts") and not r.get("unreleased")
    ]
    mature = [
        r["copies_sold"]
        for r in rows
        if isinstance(r.get("copies_sold"), (int, float))
        and r.get("release_ts")
        and (NOW - r["release_ts"]) / MONTH >= 12
    ]
    return {
        "n": n,
        "with_copies": len(copies),
        "copies_median": int(st.median(copies)) if copies else None,
        "copies_p25": int(q(copies, 0.25)) if copies else None,
        "copies_p75": int(q(copies, 0.75)) if copies else None,
        "share_copies_under_1000": round(sum(1 for c in copies if c < 1000) / len(copies), 3) if copies else None,
        "share_copies_over_100k": round(sum(1 for c in copies if c >= 100_000) / len(copies), 3) if copies else None,
        "copies_median_mature": int(st.median(mature)) if mature else None,
        "with_score": len(scores),
        "score_median": int(st.median(scores)) if scores else None,
        "share_no_reviews": round(no_score / n, 3) if n else None,
        "share_mixed_or_worse": round(low / len(scores), 3) if scores else None,
        "share_unreleased": round(unreleased / n, 3) if n else None,
        "months_since_release_median": round(st.median(ages), 1) if ages else None,
    }


def tag_outcomes(by_fest: dict[str, list[dict]], min_n: int = 150) -> list[dict]:
    """Исходы по тегам: медианный тираж и доля незамеченных."""
    buckets: dict[str, list[dict]] = collections.defaultdict(list)
    for rows in by_fest.values():
        for r in rows:
            for tag in r.get("tags") or []:
                buckets[tag].append(r)
    out = []
    for tag, rows in buckets.items():
        copies = [r["copies_sold"] for r in rows if isinstance(r.get("copies_sold"), (int, float))]
        if len(copies) < min_n:
            continue
        no_score = sum(1 for r in rows if r.get("review_score") is None)
        out.append(
            {
                "tag": tag,
                "n": len(copies),
                "copies_median": int(st.median(copies)),
                "copies_p90": int(q(copies, 0.9)),
                "share_no_reviews": round(no_score / len(rows), 3),
            }
        )
    out.sort(key=lambda r: -r["copies_median"])
    return out


def tag_trend(by_fest: dict[str, list[dict]], recent: list[str], base: str) -> list[dict]:
    """Изменение доли тега между изданием-базой и последними изданиями."""

    def share(fests: list[str], tag: str) -> float:
        total = sum(len(by_fest[f]) for f in fests)
        hit = sum(1 for f in fests for r in by_fest[f] if tag in (r.get("tags") or []))
        return 100 * hit / total if total else 0.0

    tags = {t for f in recent for r in by_fest.get(f, []) for t in (r.get("tags") or [])}
    rows = []
    for tag in tags:
        before = share([base], tag)
        after = share(recent, tag)
        rows.append({"tag": tag, "before": round(before, 2), "after": round(after, 2),
                     "delta": round(after - before, 2)})
    rows.sort(key=lambda r: -r["delta"])
    return rows


def main() -> int:
    by_fest = load()
    # список изданий — из единого календаря (src/sobs/fests.py): жёсткий список
    # уже приводил к пропаже февраля 2025 на графике составов
    order = [f.slug for f in FESTS]
    editions = {f: edition_stats(by_fest[f]) for f in order if f in by_fest}
    tags_out = tag_outcomes(by_fest)
    # базовая линия для тренда тегов: только издания с полным составом
    # (совпадает с quality == "full" в site/data/fests.json)
    full = [f for f in ("oct2024", "jun2025", "oct2025", "feb2026", "jun2026", "oct2026")
            if f in by_fest]
    trend = tag_trend(by_fest, full, "jun2021")

    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "editions": editions,
        "tags": tags_out,
        "tag_trend_vs_2021": trend,
        "notes": [
            "copies_sold — оценка Gamalytic, не наблюдение Valve",
            "тираж накопительный: у старых изданий больше времени, поэтому в отчёте "
            "есть медиана только среди игр старше 12 месяцев",
            "review_score — доля положительных отзывов; None = отзывов нет",
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    md: list[str] = ["# Анализ исходов участников Next Fest", ""]
    md.append("Сгенерировано: " + payload["generated"])
    md.append("")
    md.append("## 1. Издание → исход участника")
    md.append("")
    md.append("| Издание | участников | медиана тиража | тираж <1 000 | без отзывов | не вышло |")
    md.append("|---|---|---|---|---|---|")
    for slug, s in editions.items():
        under = "" if s["share_copies_under_1000"] is None else f"{round(100 * s['share_copies_under_1000'])}%"
        no_rev = "" if s["share_no_reviews"] is None else f"{round(100 * s['share_no_reviews'])}%"
        unr = "" if s["share_unreleased"] is None else f"{round(100 * s['share_unreleased'])}%"
        md.append(f"| {slug} | {s['n']} | {s['copies_median'] or '—'} | {under} | {no_rev} | {unr} |")
    md.append("")
    md.append("## 2. Теги: где исход хуже (n ≥ 150 игр)")
    md.append("")
    md.append("| Тег | игр | медиана тиража | p90 тиража | без отзывов |")
    md.append("|---|---|---|---|---|")
    for row in tags_out[:25]:
        md.append(f"| {row['tag']} | {row['n']} | {row['copies_median']} | {row['copies_p90']} | "
                  f"{round(100 * row['share_no_reviews'])}% |")
    md.append("")
    md.append("## 3. Доля тегов: полные издания 2024–2026 против июня 2021")
    md.append("")
    md.append("| Тег | июнь 2021 | 2024–2026 | изменение, п.п. |")
    md.append("|---|---|---|---|")
    for row in trend[:12] + trend[-6:]:
        md.append(f"| {row['tag']} | {row['before']}% | {row['after']}% | {row['delta']:+.1f} |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"изданий: {len(editions)}, тегов в разрезе исходов: {len(tags_out)}")
    print("файлы:", OUT_JSON.name, "|", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
