"""Свести все источники составов в единый датасет.

Вход:
  data/processed/nextfest/<slug>.json             — составы из HTML Wayback (2021)
  data/processed/nextfest/<slug>_lineup.json      — текущее издание (live-эндпоинт)
  data/processed/nextfest/<slug>_lineup_ajax.json — архивные XHR (2024+)

Выход:
  data/processed/nextfest_games.jsonl      — строка на (издание, игра)
  data/processed/nextfest_tag_facets.jsonl — строка на (издание, тег, число игр)
  data/processed/tags.json                 — справочник tagid -> название
  data/processed/dataset_report.json       — сводка со сверкой контрольных чисел

Запуск: python scripts/build_dataset.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import by_slug  # noqa: E402

SRC = config.OUT_DIR / "nextfest"
OUT_GAMES = config.OUT_DIR / "nextfest_games.jsonl"
OUT_FACETS = config.OUT_DIR / "nextfest_tag_facets.jsonl"
OUT_TAGS = config.OUT_DIR / "tags.json"
OUT_REPORT = config.OUT_DIR / "dataset_report.json"


def slug_of(path: Path) -> str:
    name = path.name
    for suffix in ("_lineup_ajax.json", "_lineup.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def load_candidates() -> dict[str, list[dict]]:
    """Все найденные варианты состава по изданиям."""
    cands: dict[str, list[dict]] = collections.defaultdict(list)

    for path in sorted(SRC.glob("*_lineup.json")):
        if path.name.startswith("_"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        cands[slug_of(path)].append(
            {
                "source": "live_endpoint",
                "appids": rec.get("appids", []),
                "tag_facets": rec.get("tag_facet_counts", {}),
                "snapshot": rec.get("source", {}).get("fetched_at"),
            }
        )

    for path in sorted(SRC.glob("*_lineup_ajax.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        slug = rec.get("fest_slug") or slug_of(path)
        cands[slug].append(
            {
                "source": f"wayback_xhr:{rec.get('tagid')}",
                "appids": rec.get("appids", []),
                "tag_facets": rec.get("tag_facet_counts", {}),
                "snapshot": rec.get("snapshot", {}).get("iso"),
            }
        )

    for path in sorted(SRC.glob("*.json")):
        if "_lineup" in path.name or path.name.startswith("_"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rec, dict):
            continue  # steam_tags.json и прочие справочники
        if rec.get("status") != "ok" or "games" not in rec:
            continue
        games = rec["games"]
        strategy = rec.get("strategy") or "wayback_html"
        cands[slug_of(path)].append(
            {
                # источник важен: по нему отличаем полный HTML-состав от
                # реконструкции по appid-срезам (`wayback_html_ids`)
                "source": strategy if strategy.startswith("wayback_html_ids") else "wayback_html",
                "appids": [g["appid"] for g in games],
                "tag_facets": {},
                "snapshot": rec.get("snapshot", {}).get("iso"),
                "games": games,
            }
        )
    return cands


def load_gamalytic() -> dict[int, dict]:
    """Бесплатный каталог Gamalytic: теги, жанры, цена, отзывы, тираж.

    Вишлистов в бесплатной выдаче нет (они только в платном `/game/<appid>`),
    но теги по каждому appid — именно то, чего не хватало изданиям 2024+.
    """
    path = config.OUT_DIR / "gamalytic_games.jsonl"
    out: dict[int, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
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


def pick_best(cands: list[dict], expected: int | None) -> dict:
    """Выбрать состав: ближайший к контрольному числу (иначе — самый большой).

    При равной близости предпочитаем живой эндпоинт (это финальный состав издания),
    затем архивный XHR, затем HTML-архив. Так press preview (зарегистрированные
    игры) не подменяет финальный состав фестиваля.
    """
    priority = {"live_endpoint": 0, "wayback_xhr": 1, "wayback_html": 2}

    def key(c: dict) -> tuple:
        n = len(c["appids"])
        diff = abs(n - expected) / expected if expected else 0.0
        src = c["source"].split(":")[0]
        return (round(diff, 4), priority.get(src, 9), -n)

    return min(cands, key=key)


def main() -> int:
    cands = load_candidates()
    gamalytic = load_gamalytic()
    tags: dict[int, str] = {}

    tag_file = SRC / "steam_tags.json"
    if tag_file.exists():
        for item in json.loads(tag_file.read_text(encoding="utf-8")):
            if isinstance(item, dict) and "tagid" in item:
                tags[int(item["tagid"])] = item.get("name", "")

    extra_file = SRC / "_tags_extra.json"
    if extra_file.exists():
        for tid, name in json.loads(extra_file.read_text(encoding="utf-8")).items():
            tags.setdefault(int(tid), name)

    rows_games = rows_facets = 0
    report = []

    with OUT_GAMES.open("w", encoding="utf-8") as fg, OUT_FACETS.open("w", encoding="utf-8") as ff:
        for slug, items in sorted(cands.items()):
            try:
                fest = by_slug(slug)
            except KeyError:
                fest = None
            best = pick_best(items, fest.expected if fest else None)
            game_meta = {g["appid"]: g for g in best.get("games", [])}

            exp_check = fest.expected if fest else None
            n_best = len(best["appids"])
            # Составы, восстановленные по appid из архивных снапшотов, заведомо
            # неполные: страница отдавала только первый срез списка. Если есть
            # контрольное число и покрытие ниже 90% — это «partial» (показываем
            # как «≥ N»), если контроля нет — «reconstructed» (полнота неизвестна).
            ids_based = best["source"].startswith("wayback_html_ids")
            partial = ids_based and bool(exp_check) and n_best < 0.9 * exp_check
            reconstructed = ids_based and not exp_check
            quality = "partial" if partial else "reconstructed" if reconstructed else "full"
            # Контроль качества: если состав расходится с контрольным числом больше
            # чем на 25%, он неполный или захватывает лишние записи — не публикуем.
            unreliable = (
                bool(exp_check)
                and abs(n_best - exp_check) / exp_check > 0.25
                and quality == "full"
            )

            # Фасеты тегов: у XHR-снимков они есть готовыми, у HTML-составов
            # считаем сами по тегам игр — иначе издания 2021 и частичные
            # остаются без раздела «насыщенность тегов».
            facet_counts: dict = dict(best.get("tag_facets") or {})
            facets_from = "xhr" if facet_counts else "games"
            if not facet_counts:
                facet_counts = dict(
                    collections.Counter(
                        int(tid)
                        for g in best.get("games", [])
                        for tid in (g.get("tag_ids") or [])
                    )
                )

            for appid in ([] if unreliable else best["appids"]):
                meta = game_meta.get(appid, {})
                gm = gamalytic.get(appid, {})
                for tid in meta.get("tag_ids") or []:
                    tags.setdefault(int(tid), "")
                fg.write(
                    json.dumps(
                        {
                            "fest": slug,
                            "appid": appid,
                            "title": meta.get("title") or gm.get("name") or "",
                            "tags": meta.get("tags") or gm.get("tags") or [],
                            "genres": gm.get("genres") or [],
                            "release": meta.get("release", ""),
                            "release_ts": gm.get("releaseDate"),
                            "is_free": meta.get("is_free"),
                            "price_cents": meta.get("price_cents"),
                            "review_score": gm.get("reviewScore"),
                            "copies_sold": gm.get("copiesSold"),
                            "unreleased": gm.get("unreleased"),
                            "source": best["source"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                rows_games += 1

            for tid, cnt in ({} if unreliable else facet_counts).items():
                ff.write(
                    json.dumps(
                        {
                            "fest": slug,
                            "tagid": int(tid),
                            "games": int(cnt),
                            "source": best["source"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                rows_facets += 1

            n = len(best["appids"])
            exp = fest.expected if fest else None
            report.append(
                {
                    "fest": slug,
                    "label_ru": fest.label_ru if fest else slug,
                    "label_en": fest.label_en if fest else slug,
                    "season": fest.season if fest else None,
                    "year": fest.year if fest else None,
                    "chosen_source": best["source"],
                    "snapshot": best.get("snapshot"),
                    "n_appids": n,
                    "expected": exp,
                    "status": "unreliable" if unreliable else "ok",
                    "quality": quality,
                    "facets_from": facets_from,
                    "diff_pct": round(100 * (n - exp) / exp, 1) if exp and n else None,
                    "candidates": [
                        {"source": c["source"], "n": len(c["appids"]), "snapshot": c.get("snapshot")}
                        for c in sorted(items, key=lambda c: -len(c["appids"]))
                    ],
                }
            )

    OUT_TAGS.write_text(json.dumps(tags, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'издание':10} {'выбрано':>8} {'контроль':>9} {'разница':>8}  источник")
    print("-" * 74)
    for r in sorted(report, key=lambda x: (x["year"] or 0, x["fest"])):
        diff = f"{r['diff_pct']}%" if r["diff_pct"] is not None else "—"
        print(
            f"{r['fest']:10} {r['n_appids']:>8} {r['expected'] or '—':>9} {diff:>8}  {r['chosen_source']}"
        )
    print(f"\nигр: {rows_games}, строк по тегам: {rows_facets}, тегов: {len(tags)}")
    print(f"файлы: {OUT_GAMES.name}, {OUT_FACETS.name}, {OUT_TAGS.name}, {OUT_REPORT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
