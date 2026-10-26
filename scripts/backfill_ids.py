"""Восстановить состав издания по appid-множествам из архивных снапшотов.

Почему отдельный скрипт: страницы Next Fest 2021–2023 отдавали в HTML лишь
ПЕРВУЮ часть списка — маппинг `{"appid":N,"demo_appid":M}` (обычно 300–320
записей), остальное подгружалось XHR, которого в Wayback нет. Зато снапшотов
много, и в каждом свой срез, поэтому объединение даёт больше.

Запуск:
    python scripts/backfill_ids.py --only oct2021 --probe   # что даёт каждый снапшот
    python scripts/backfill_ids.py                          # все издания без состава
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import FESTS, by_slug  # noqa: E402
from sobs.parse import _unescape_variants, extract_games  # noqa: E402
from sobs.sources import wayback  # noqa: E402

log = logging.getLogger("backfill_ids")

OUT_NEXTFEST = config.OUT_DIR / "nextfest"

# пары «игра -> демо» — основной след состава на странице
PAIR_RE = re.compile(r'"appid"\s*:\s*(\d+)\s*,\s*"demo_appid"\s*:\s*(\d+)')
# карточка игры целиком: {"appid":N,"type":"game",...,"title":...}
CARD_RE = re.compile(r'\{\s*"appid"\s*:\s*(\d+)\s*,\s*"type"\s*:')


def _ts(d: date, end: bool = False) -> str:
    return d.strftime("%Y%m%d") + ("235959" if end else "000000")


def scan_snapshot(html: str) -> tuple[set[int], dict[int, int]]:
    """appid'ы и пары appid->demo_appid из одного снапшота (берём лучший вариант)."""
    best: tuple[int, set[int], dict[int, int]] = (0, set(), {})
    for _name, text in _unescape_variants(html):
        pairs = {int(a): int(b) for a, b in PAIR_RE.findall(text)}
        cards = {int(a) for a in CARD_RE.findall(text)}
        ids = set(pairs) | cards
        if len(ids) > best[0]:
            best = (len(ids), ids, pairs)
        if len(ids) > 400:  # дальше варианты уже не дадут большего
            break
    return best[1], best[2]


def backfill(fest, *, max_snapshots: int, probe: bool = False) -> dict:
    start = date.fromisoformat(fest.start)
    window = (start - timedelta(days=2), start + timedelta(days=40))
    snaps = wayback.cdx(
        config.NEXTFEST_PAGE,
        from_ts=_ts(window[0]),
        to_ts=_ts(window[1], end=True),
        limit=400,
    )
    snaps.sort(key=lambda s: s.length, reverse=True)
    log.info("%s: снапшотов %d", fest.slug, len(snaps))

    all_ids: set[int] = set()
    demo_map: dict[int, int] = {}
    used: list[dict] = []
    titles: dict[int, str] = {}
    title_attempts = 0

    for snap in snaps[:max_snapshots]:
        if snap.length < 15_000:
            continue
        try:
            html = wayback.fetch_snapshot(snap)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s: снапшот %s не скачался: %s", fest.slug, snap.timestamp, exc)
            continue
        ids, pairs = scan_snapshot(html)
        before = len(all_ids)
        all_ids |= ids
        for a, d in pairs.items():
            demo_map.setdefault(a, d)
        used.append(
            {
                "timestamp": snap.timestamp,
                "iso": snap.iso,
                "n_ids": len(ids),
                "n_new": len(all_ids) - before,
            }
        )
        if probe:
            print(f"   {snap.timestamp} ({snap.length // 1024} КБ): {len(ids)} id, "
                  f"+{len(all_ids) - before} новых, всего {len(all_ids)}")

        # Названия вытаскиваем только на первых снапшотах: полный разбор страницы
        # дорогой (десятки секунд на файл), а в изданиях 2022–2023 названий в HTML
        # нет вообще. Названия и теги к найденным appid добавляет enrich_lineup_ids.py.
        if title_attempts < 3 and len(titles) < 60:
            title_attempts += 1
            try:
                games_raw, _ = extract_games(html)
            except Exception:  # noqa: BLE001
                games_raw = []
            for g in games_raw:
                t = g.get("title") or g.get("name")
                if t and g.get("appid"):
                    titles.setdefault(int(g["appid"]), t)

    all_ids = {a for a in all_ids if a > 1000}
    record = {
        "fest": fest.slug,
        "label_en": fest.label_en,
        "label_ru": fest.label_ru,
        "year": fest.year,
        "expected": fest.expected,
        "n_ids": len(all_ids),
        "appids": sorted(all_ids),
        "demo_map": {str(k): v for k, v in sorted(demo_map.items())},
        "titles": {str(k): v for k, v in sorted(titles.items())},
        "snapshots": used,
    }
    OUT_NEXTFEST.mkdir(parents=True, exist_ok=True)
    (OUT_NEXTFEST / f"{fest.slug}_ids.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", help="slug издания (можно несколько)")
    ap.add_argument("--max-snapshots", type=int, default=12)
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.only:
        fests = [by_slug(s) for s in args.only]
    else:
        have = {p.name.replace(".json", "") for p in OUT_NEXTFEST.glob("*.json")}
        fests = [f for f in FESTS if f.slug not in have]

    print(f"{'издание':9} {'appid':>7} {'контроль':>9}")
    for fest in fests:
        rec = backfill(fest, max_snapshots=args.max_snapshots, probe=args.probe)
        print(f"{fest.slug:9} {rec['n_ids']:>7} {fest.expected or '—':>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
