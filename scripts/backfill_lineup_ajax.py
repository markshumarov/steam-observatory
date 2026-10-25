"""Восстановить составы прошлых фестивалей из архивированных XHR-ответов.

Wayback сохранил ответы `actions/ajaxgetdynamicsaleitems` (тот самый эндпоинт,
что отдаёт полный состав). Здесь мы находим их по CDX, группируем по
`tagids_featured` (у каждого события свой тег) и, с флагом --fetch,
скачиваем и разбираем состав.

Запуск:
    python scripts/backfill_lineup_ajax.py              # только обзор снапшотов
    python scripts/backfill_lineup_ajax.py --fetch      # + скачать и разобрать
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import FESTS  # noqa: E402
from sobs.http import get_text  # noqa: E402
from sobs.sources import wayback  # noqa: E402

ENDPOINT = "store.steampowered.com/actions/ajaxgetdynamicsaleitems"
TAGID_RE = re.compile(r"tagids_featured=(\d+)")


def collect(from_ts: str, to_ts: str) -> dict[str, list[wayback.Snapshot]]:
    snaps = wayback.cdx(ENDPOINT, from_ts=from_ts, to_ts=to_ts, limit=1500, match_type="prefix")
    by_tag: dict[str, list[wayback.Snapshot]] = collections.defaultdict(list)
    for s in snaps:
        m = TAGID_RE.search(unquote(s.original))
        if m:
            by_tag[m.group(1)].append(s)
    return by_tag


def parse_snapshot(snap: wayback.Snapshot) -> dict | None:
    try:
        body = get_text(snap.raw_url, suffix=".json")
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        return None
    capsules = data.get("rgCapsules") or []
    appids = [int(c["id"]) for c in capsules if isinstance(c, dict) and c.get("type") == "game"]
    if not appids:
        return None
    return {
        "snapshot": {"timestamp": snap.timestamp, "iso": snap.iso, "url": snap.raw_url},
        "n_appids": len(appids),
        "appids": appids,
        "n_match_count": data.get("nMatchCount"),
        "more_results_remaining": data.get("bMoreResultsRemaining"),
        "tag_facet_counts": {int(k): int(v) for k, v in (data.get("rgSolrFacetCounts") or {}).items()},
    }


def guess_fest(snap_iso: str):
    """Ближайшее издание по дате снапшота.

    Wayback сохраняет XHR не строго в дни фестиваля, поэтому берём ближайшее
    издание в окне ±75 дней от старта. Итоговое имя издания проверяем по числу
    участников (см. `expected` в fests.py).
    """
    d = date.fromisoformat(snap_iso[:10])
    best = None
    best_delta: int | None = None
    for fest in FESTS:
        start = date.fromisoformat(fest.start)
        delta = abs((d - start).days)
        if delta <= 75 and (best_delta is None or delta < best_delta):
            best, best_delta = fest, delta
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="20230101")
    ap.add_argument("--to", dest="to", default="20261027")
    ap.add_argument("--fetch", action="store_true", help="скачать и разобрать составы")
    args = ap.parse_args()

    by_tag = collect(args.frm, args.to)
    print(f"тегов (tagids_featured): {len(by_tag)}\n")
    print(f"{'tagid':>10} {'snaps':>6} {'макс.КБ':>8}  период")
    for tagid, snaps in sorted(by_tag.items(), key=lambda kv: -max(s.length for s in kv[1])):
        snaps.sort(key=lambda s: s.timestamp)
        print(
            f"{tagid:>10} {len(snaps):>6} {max(s.length for s in snaps) // 1024:>8}  "
            f"{snaps[0].iso[:10]} .. {snaps[-1].iso[:10]}"
        )

    if not args.fetch:
        return 0

    out_dir = config.OUT_DIR / "nextfest"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for tagid, snaps in by_tag.items():
        snaps.sort(key=lambda s: s.length, reverse=True)
        best = None
        for snap in snaps[:4]:
            rec = parse_snapshot(snap)
            if rec and (best is None or rec["n_appids"] > best["n_appids"]):
                best = rec
        if not best:
            continue
        fest = guess_fest(best["snapshot"]["iso"])
        rec = {"tagid": tagid, "fest_slug": fest.slug if fest else None, **best}
        results.append(rec)
        name = fest.slug if fest else f"unknown_{tagid}"
        (out_dir / f"{name}_lineup_ajax.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        exp = fest.expected if fest else None
        print(f"{name:16} appid={rec['n_appids']:>6}  ожидалось={exp}")

    (out_dir / "_lineup_ajax_report.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "appids"} for r in results],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\nсоставов разобрано: {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
