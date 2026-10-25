"""Добавить названия и теги к составам, восстановленным по appid (`*_ids.json`).

В HTML 2021–2023 у игр нет названий и тегов — только appid. Берём их из
бесплатного каталога Gamalytic (`gamalytic_games.jsonl`), при отсутствии —
из Steam appdetails (по одному запросу, поэтому только для остатка).

Теги Steam приходят названиями; переводим в tagid по справочнику `steam_tags.json`,
а незнакомые сохраняем в `_tags_extra.json` с устойчивым отрицательным id.

Выход: `data/processed/nextfest/<slug>.json` — тот же формат, что у HTML-бэкфилла,
поэтому `build_dataset.py` подхватывает его без изменений.

Запуск: python scripts/enrich_lineup_ids.py [--no-appdetails]
"""

from __future__ import annotations

import glob
import json
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import by_slug  # noqa: E402
from sobs.sources import steam  # noqa: E402

NEXTFEST = config.OUT_DIR / "nextfest"
GAMALYTIC = config.OUT_DIR / "gamalytic_games.jsonl"


def load_gamalytic() -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not GAMALYTIC.exists():
        return out
    for line in GAMALYTIC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        appid = rec.get("steamId") or rec.get("id")
        if appid:
            out[int(appid)] = rec
    return out


def load_tag_dict() -> tuple[dict[str, int], dict[int, str]]:
    """(название -> tagid, tagid -> название) из собранного справочника."""
    by_name: dict[str, int] = {}
    by_id: dict[int, str] = {}
    path = NEXTFEST / "steam_tags.json"
    if path.exists():
        for item in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(item, dict) and item.get("tagid") and item.get("name"):
                by_id[int(item["tagid"])] = item["name"]
                by_name.setdefault(item["name"].lower(), int(item["tagid"]))
    return by_name, by_id


def stable_id(name: str) -> int:
    return -abs(zlib.crc32(name.encode("utf-8")) % 1_000_000)


def enrich(slug: str, gamalytic: dict[int, dict], by_name: dict[str, int],
           extra: dict[int, str], use_appdetails: bool) -> dict | None:
    path = NEXTFEST / f"{slug}_ids.json"
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    fest = by_slug(slug)
    titles = {int(k): v for k, v in (rec.get("titles") or {}).items()}
    demo_map = rec.get("demo_map") or {}

    games: list[dict] = []
    missing: list[int] = []
    for appid in rec["appids"]:
        gm = gamalytic.get(appid) or {}
        title = titles.get(appid) or gm.get("name") or ""
        raw_tags = [t for t in (gm.get("tags") or []) if isinstance(t, str)]
        tag_ids = []
        for name in raw_tags:
            tid = by_name.get(name.lower())
            if tid is None:
                tid = stable_id(name)
                extra.setdefault(tid, name)
            tag_ids.append(tid)
        if not title:
            missing.append(appid)
        price = gm.get("price")
        games.append(
            {
                "appid": appid,
                "title": title,
                "type": "game",
                "release": gm.get("releaseDate") or "",
                "tags": raw_tags,
                "tag_ids": tag_ids,
                "is_free": (price == 0) if price is not None else None,
                "price_cents": int(price * 100) if price else None,
                "demo_appid": demo_map.get(str(appid)),
                "source": "gamalytic",
            }
        )

    if use_appdetails and missing:
        print(f"  {slug}: appdetails для {len(missing)} игр без названия", flush=True)
        by_appid = {g["appid"]: g for g in games}
        for i, appid in enumerate(missing, 1):
            try:
                data = steam.appdetails([appid], filters="basic")
                item = (data or {}).get(str(appid)) or {}
                if item.get("success"):
                    d = item.get("data") or {}
                    g = by_appid[appid]
                    g["title"] = d.get("name") or ""
                    g["release"] = (d.get("release_date") or {}).get("date") or g["release"]
            except Exception:  # noqa: BLE001 — название просто останется пустым
                pass
            if i % 50 == 0:
                print(f"    {i}/{len(missing)}", flush=True)
            time.sleep(0.7)

    named = sum(1 for g in games if g["title"])
    tagged = sum(1 for g in games if g["tag_ids"])
    out = {
        "fest": {
            "slug": slug,
            "label_en": fest.label_en,
            "label_ru": fest.label_ru,
            "season": fest.season,
            "year": fest.year,
            "start": fest.start,
            "end": fest.end,
            "expected_participants": fest.expected,
        },
        "snapshot": {"timestamp": ", ".join(s["timestamp"] for s in rec.get("snapshots", [])[:3])},
        "page_title": f"Steam Next Fest | {fest.label_en}",
        "strategy": "wayback_html_ids+gamalytic",
        "n_games": len(games),
        "n_objects": len(rec["appids"]),
        "n_named": named,
        "n_tagged": tagged,
        "games": games,
        "status": "ok",
    }
    (NEXTFEST / f"{slug}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return {"slug": slug, "n": len(games), "named": named, "tagged": tagged,
            "expected": fest.expected}


def main() -> int:
    use_appdetails = "--no-appdetails" not in sys.argv
    gamalytic = load_gamalytic()
    by_name, _by_id = load_tag_dict()
    extra: dict[int, str] = {}
    print(f"каталог Gamalytic: {len(gamalytic)} игр", flush=True)

    results = []
    for path in sorted(glob.glob(str(NEXTFEST / "*_ids.json"))):
        slug = Path(path).name.replace("_ids.json", "")
        res = enrich(slug, gamalytic, by_name, extra, use_appdetails)
        if res:
            results.append(res)

    if extra:
        (NEXTFEST / "_tags_extra.json").write_text(
            json.dumps({str(k): v for k, v in sorted(extra.items())}, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"{'издание':9} {'игр':>6} {'названий':>9} {'с тегами':>9} {'контроль':>9}")
    for r in results:
        print(f"{r['slug']:9} {r['n']:>6} {r['named']:>9} {r['tagged']:>9} "
              f"{r['expected'] or '—':>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

