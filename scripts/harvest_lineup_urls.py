"""Добрать состав издания из ВСЕХ архивных вариантов страницы фестиваля.

Страница отдавала в HTML только первый срез списка, но в архиве лежат не только
`/sale/nextfest`, а и десятки её вариантов: `?tab=N`, `?facetsNNNN=x:y`, `?l=...`.
Каждый вариант — своя выборка, поэтому объединение appid из всех вариантов даёт
больше, чем обход одного URL (так октябрь 2021 дал 598 записей).

Скрипт дополняет уже существующий `<slug>_ids.json` (не перезаписывая найденное),
поэтому дальше конвейер работает без изменений: enrich -> build_dataset.

Запуск:
    python scripts/harvest_lineup_urls.py --only jun2023 --probe
    python scripts/harvest_lineup_urls.py --only jun2023 --only oct2023
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
from sobs.fests import by_slug  # noqa: E402
from sobs.parse import _unescape_variants  # noqa: E402
from sobs.sources import wayback  # noqa: E402

log = logging.getLogger("harvest")

OUT_NEXTFEST = config.OUT_DIR / "nextfest"
PAIR_RE = re.compile(r'"appid"\s*:\s*(\d+)\s*,\s*"demo_appid"\s*:\s*(\d+)')
CARD_RE = re.compile(r'\{\s*"appid"\s*:\s*(\d+)\s*,\s*"type"\s*:')


def _ts(d: date, end: bool = False) -> str:
    return d.strftime("%Y%m%d") + ("235959" if end else "000000")


def scan(html: str) -> tuple[set[int], dict[int, int]]:
    """appid'ы и пары appid->demo_appid из одного снапшота."""
    best: tuple[int, set[int], dict[int, int]] = (0, set(), {})
    for _name, text in _unescape_variants(html):
        pairs = {int(a): int(b) for a, b in PAIR_RE.findall(text)}
        cards = {int(a) for a in CARD_RE.findall(text)}
        ids = set(pairs) | cards
        if len(ids) > best[0]:
            best = (len(ids), ids, pairs)
        if len(ids) > 400:
            break
    return best[1], best[2]


def url_candidates(fest, *, limit: int) -> list[wayback.Snapshot]:
    """Все снапшоты всех вариантов страницы фестиваля в окне издания."""
    start = date.fromisoformat(fest.start)
    window = (start - timedelta(days=2), start + timedelta(days=40))
    snaps = wayback.cdx(
        config.NEXTFEST_PAGE,
        from_ts=_ts(window[0]),
        to_ts=_ts(window[1], end=True),
        limit=limit,
        match_type="prefix",
    )
    return snaps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", required=True)
    ap.add_argument("--limit", type=int, default=2000, help="сколько строк CDX брать")
    ap.add_argument("--per-url", type=int, default=3, help="снапшотов на вариант URL")
    ap.add_argument("--max-urls", type=int, default=0, help="ограничить число вариантов URL (0 — все)")
    ap.add_argument("--min-size", type=int, default=150_000)
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    for slug in args.only:
        fest = by_slug(slug)
        ids_path = OUT_NEXTFEST / f"{slug}_ids.json"
        rec = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else None
        base_ids = set(rec["appids"]) if rec else set()
        demo_map = {int(k): v for k, v in (rec.get("demo_map") or {}).items()} if rec else {}
        titles = {int(k): v for k, v in (rec.get("titles") or {}).items()} if rec else {}

        snaps = url_candidates(fest, limit=args.limit)
        by_url: dict[str, list] = {}
        for s in snaps:
            by_url.setdefault(s.raw_url.split("id_/")[-1], []).append(s)
        if args.max_urls:
            by_url = dict(sorted(by_url.items(), key=lambda kv: -max(x.length for x in kv[1]))[: args.max_urls])
        log.info("%s: снапшотов %d, вариантов URL %d", slug, len(snaps), len(by_url))

        added = 0
        for url, items in by_url.items():
            items.sort(key=lambda s: s.length, reverse=True)
            for snap in items[: args.per_url]:
                if snap.length < args.min_size:
                    continue
                try:
                    html = wayback.fetch_snapshot(snap)
                except Exception as exc:  # noqa: BLE001
                    log.warning("%s: %s не скачался: %s", slug, snap.timestamp, exc)
                    continue
                ids, pairs = scan(html)
                new = ids - base_ids
                if args.probe:
                    print(f"   {url[:88]:88} {snap.timestamp} +{len(new)} (всего {len(base_ids)})",
                          flush=True)
                base_ids |= ids
                for a, d in pairs.items():
                    demo_map.setdefault(a, d)
                added += len(new)

        base_ids = {a for a in base_ids if a > 1000}
        if rec is not None:
            rec["appids"] = sorted(base_ids)
            rec["demo_map"] = {str(k): v for k, v in sorted(demo_map.items())}
            rec["titles"] = {str(k): v for k, v in sorted(titles.items())}
            rec["n_ids"] = len(base_ids)
            rec["harvest_urls"] = len(by_url)
            ids_path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        print(f"{slug}: appid {len(base_ids)} (новых {added}), вариантов URL {len(by_url)}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
