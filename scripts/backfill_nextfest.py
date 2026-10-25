"""Бэкфилл составов Steam Next Fest из Wayback Machine (2021 -> сейчас).

Для каждого издания фестиваля:
1. ищем снапшоты страницы /sale/nextfest в окне вокруг дат фестиваля;
2. берём самые «тяжёлые» снапшоты (в них лежит полный список участников);
3. парсим JSON участников, нормализуем, сохраняем;
4. сверяем число участников с контрольными данными (GameDiscoverCo / HTMAG).

Запуск:
    python scripts/backfill_nextfest.py                 # все издания
    python scripts/backfill_nextfest.py --only oct2026  # одно издание
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import FESTS, Fest, by_slug  # noqa: E402
from sobs.parse import extract_games, normalize_game, page_title  # noqa: E402
from sobs.sources import wayback  # noqa: E402

log = logging.getLogger("backfill")

OUT_NEXTFEST = config.OUT_DIR / "nextfest"
RAW_NEXTFEST = config.RAW_DIR / "nextfest"


def _ts(d: date, end: bool = False) -> str:
    return d.strftime("%Y%m%d") + ("235959" if end else "000000")


def backfill_fest(fest: Fest, *, min_games: int = 50, candidates: int = 6) -> dict:
    start = date.fromisoformat(fest.start)
    # окно: чуть до старта и до 45 дней после — страница держит состав
    # последнего фестиваля до следующего, поэтому пост-фестовые снапшоты валидны.
    window = (start - timedelta(days=2), start + timedelta(days=45))

    snaps = wayback.cdx(
        config.NEXTFEST_PAGE,
        from_ts=_ts(window[0]),
        to_ts=_ts(window[1], end=True),
        limit=400,
    )
    snaps.sort(key=lambda s: s.length, reverse=True)
    log.info("%s: найдено снапшотов: %d", fest.slug, len(snaps))

    best: dict | None = None
    for snap in snaps[:candidates]:
        if snap.length < 20_000:
            continue
        try:
            html = wayback.fetch_snapshot(snap)
        except Exception as exc:  # noqa: BLE001 — фиксируем и идём дальше
            log.warning("%s: снапшот %s не скачался: %s", fest.slug, snap.timestamp, exc)
            continue

        games_raw, strategy = extract_games(html)
        title = page_title(html)
        # Отсеиваем «мусорные» объекты страницы (трансляции, мэппинг демо и т.п.):
        # карточка игры всегда имеет название и теги/капсулу.
        valid = [
            g
            for g in games_raw
            if (g.get("title") or g.get("name"))
            and (
                g.get("tags")
                or g.get("capsule")
                or g.get("tiny_capsule")
                or g.get("main_capsule")
            )
        ]
        log.info(
            "%s: снапшот %s (%d КБ) -> объектов %d, из них карточек игр %d, стратегия %s, заголовок %r",
            fest.slug,
            snap.timestamp,
            snap.length // 1024,
            len(games_raw),
            len(valid),
            strategy,
            title,
        )
        if len(valid) < min_games:
            continue
        if best is None or len(valid) > best["n_games"]:
            best = {
                "snapshot": {
                    "timestamp": snap.timestamp,
                    "iso": snap.iso,
                    "url": snap.raw_url,
                    "cdx_length": snap.length,
                },
                "page_title": title,
                "strategy": strategy,
                "n_games": len(valid),
                "n_objects": len(games_raw),
                "games": [normalize_game(g) for g in valid],
                "html": html,
            }

    if best is None:
        return {"fest": fest.slug, "status": "no_data", "n_games": 0}

    html = best.pop("html")
    RAW_NEXTFEST.mkdir(parents=True, exist_ok=True)
    (RAW_NEXTFEST / f"{fest.slug}_{best['snapshot']['timestamp']}.html").write_bytes(
        html.encode("utf-8", "replace")
    )

    record = {
        "fest": {
            "slug": fest.slug,
            "label_en": fest.label_en,
            "label_ru": fest.label_ru,
            "season": fest.season,
            "year": fest.year,
            "start": fest.start,
            "end": fest.end,
            "expected_participants": fest.expected,
        },
        **best,
        "status": "ok",
    }
    OUT_NEXTFEST.mkdir(parents=True, exist_ok=True)
    (OUT_NEXTFEST / f"{fest.slug}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="slug издания, напр. oct2026")
    ap.add_argument("--min-games", type=int, default=50)
    ap.add_argument("--candidates", type=int, default=6)
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    fests = [by_slug(args.only)] if args.only else FESTS
    OUT_NEXTFEST.mkdir(parents=True, exist_ok=True)
    report = []
    print(f"\n{'fest':9} {'games':>6} {'expect':>7} {'diff':>7}  {'strategy':11} title")
    print("-" * 96)
    for fest in fests:
        rec = backfill_fest(fest, min_games=args.min_games, candidates=args.candidates)
        n = rec.get("n_games", 0)
        exp = fest.expected
        diff = f"{100 * (n - exp) / exp:+.0f}%" if exp and n else "—"
        print(
            f"{fest.slug:9} {n:>6} {exp if exp else '—':>7} {diff:>7}  "
            f"{rec.get('strategy', '-'):11} {rec.get('page_title', '')[:44]}"
        )
        report.append({k: v for k, v in rec.items() if k != "games"})

    (OUT_NEXTFEST / "_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    ok = sum(1 for r in report if r.get("status") == "ok")
    print(f"\nГотово: {ok}/{len(report)} изданий с данными. Отчёт: {OUT_NEXTFEST / '_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
