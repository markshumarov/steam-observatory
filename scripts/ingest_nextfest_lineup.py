"""Зафиксировать состав текущего Next Fest + гистограмму тегов.

Источник: `actions/ajaxgetdynamicsaleitems` (тот же запрос, что делает страница).

Запуск: python scripts/ingest_nextfest_lineup.py [slug] [tagid]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import by_slug  # noqa: E402
from sobs.http import get_json  # noqa: E402
from sobs.sources import steam  # noqa: E402

slug = sys.argv[1] if len(sys.argv) > 1 else "oct2026"
tagid = sys.argv[2] if len(sys.argv) > 2 else steam.NEXTFEST_TAGID

fest = by_slug(slug)
out_dir = config.OUT_DIR / "nextfest"
out_dir.mkdir(parents=True, exist_ok=True)

data = steam.dynamic_sale_items(tagid)
capsules = data.get("rgCapsules", [])
appids = [int(c["id"]) for c in capsules if c.get("type") == "game"]
facets = {int(k): int(v) for k, v in (data.get("rgSolrFacetCounts") or {}).items()}

record = {
    "slug": slug,
    "fest": {
        "label_en": fest.label_en,
        "label_ru": fest.label_ru,
        "season": fest.season,
        "year": fest.year,
        "start": fest.start,
        "end": fest.end,
        "expected_participants": fest.expected,
    },
    "source": {
        "endpoint": "store.steampowered.com/actions/ajaxgetdynamicsaleitems",
        "tagids_featured": tagid,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    },
    "n_match_count": data.get("nMatchCount"),
    "more_results_remaining": data.get("bMoreResultsRemaining"),
    "n_appids": len(appids),
    "appids": appids,
    "tag_facet_counts": facets,
}
(out_dir / f"{slug}_lineup.json").write_text(
    json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
)

# Справочник тегов: tagid -> название (публичный JSON магазина).
tags_path = out_dir / "steam_tags.json"
if not tags_path.exists():
    try:
        tags = get_json(f"{config.STEAM_STORE}/tagdata/populartags/english", suffix=".json")
        if isinstance(tags, list) and tags:
            tags_path.write_text(json.dumps(tags, ensure_ascii=False), encoding="utf-8")
            print(f"справочник тегов: {len(tags)} записей")
    except Exception as exc:  # noqa: BLE001
        print("справочник тегов не получен:", exc)

print(f"{slug}: appid={len(appids)}, тегов в гистограмме={len(facets)}, "
      f"nMatchCount={data.get('nMatchCount')}, остаток={data.get('bMoreResultsRemaining')}")
print("файл:", out_dir / f"{slug}_lineup.json")
