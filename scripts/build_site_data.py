"""Собрать компактные JSON для статического сайта.

Вход (результаты `build_dataset.py` и сбора CCU):
  data/processed/dataset_report.json
  data/processed/nextfest_tag_facets.jsonl
  data/processed/tags.json
  data/processed/nextfest/<slug>_demo_ccu.jsonl

Выход (папка site/data/):
  fests.json        — издания: состав финальный/preview, контроль, источник
  tags.json         — справочник tagid -> название
  tag_counts.json   — {издание: {tagid: число игр}}
  ccu.json          — пики CCU по демо (если данные уже есть)

Запуск: python scripts/build_site_data.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.http import get_json  # noqa: E402

SITE_DATA = config.ROOT / "site" / "data"


import re as _re

CLEAN_RE = _re.compile(r"^(Save \d+% on |Pre-purchase |Buy |Купить |Comprar |Acheter )", _re.I)
JUNK = {"Sign In", "Site Error", "Steam", "Steam Community", "Welcome to Steam", "Ошибка"}


def clean_title(raw: str) -> str:
    """«Save 10% on Tropico 7 on Steam» -> «Tropico 7»."""
    name = (raw or "").strip()
    name = CLEAN_RE.sub("", name)
    if name.endswith(" on Steam"):
        name = name[: -len(" on Steam")]
    return "" if name in JUNK else name


def resolve_names() -> dict[int, str]:
    """Названия игр: из собранных данных (страницы магазина), плюс попытка API Steam."""
    names: dict[int, str] = {}

    games_path = config.OUT_DIR / "nextfest_games.jsonl"
    if games_path.exists():
        for line in games_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("title"):
                names.setdefault(int(rec["appid"]), rec["title"])

    map_path = config.OUT_DIR / "nextfest" / "oct2026_demo_map.jsonl"
    if map_path.exists():
        for line in map_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            title = clean_title(rec.get("name", ""))
            if title:
                names[int(rec["appid"])] = title
                if rec.get("demo_appid"):
                    names.setdefault(int(rec["demo_appid"]), title)

    try:
        data = get_json(f"{config.STEAM_API}/ISteamApps/GetAppList/v2/", suffix=".json")
        for a in (data.get("applist") or {}).get("apps") or []:
            if a.get("name"):
                names.setdefault(int(a["appid"]), a["name"])
    except Exception:  # noqa: BLE001 — эндпоинт Valve часто недоступен, это не критично
        pass

    return names


def main() -> int:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    report = json.loads((config.OUT_DIR / "dataset_report.json").read_text(encoding="utf-8"))

    fests = []
    for r in report:
        if r.get("status") == "unreliable":
            print(f"пропущено издание {r['fest']}: расхождение с контролем "
                  f"{r['diff_pct']}% — данные неполные")
            continue
        # preview = самый большой кандидат, который заметно больше финального
        final_n = r["n_appids"]
        preview = None
        for c in r.get("candidates", []):
            if c["n"] > final_n * 1.05:
                preview = {"n": c["n"], "source": c["source"], "snapshot": c.get("snapshot")}
                break

        note_ru = None
        note_en = None
        if r.get("quality") == "partial":
            note_ru = "частичный состав: архивная страница отдавала только первую часть списка"
            note_en = "partial lineup: the archived page served only the first slice"
        elif r.get("quality") == "reconstructed":
            note_ru = "состав восстановлен по срезам архивной страницы; полнота неизвестна"
            note_en = "rebuilt from archived page slices; completeness unknown"
        elif r.get("diff_pct") is not None and abs(r["diff_pct"]) > 5:
            note_ru = f"расхождение с контролем {r['diff_pct']:+.1f}%"
            note_en = f"{r['diff_pct']:+.1f}% off control"

        fests.append(
            {
                "slug": r["fest"],
                "label_ru": r["label_ru"],
                "label_en": r.get("label_en") or r["label_ru"],
                "season": r["season"],
                "year": r["year"],
                "n_final": final_n,
                "n_preview": preview["n"] if preview else None,
                "expected": r["expected"],
                "diff_pct": r["diff_pct"],
                "source": r["chosen_source"],
                "quality": r.get("quality", "full"),
                "facets_from": r.get("facets_from"),
                "note_ru": note_ru,
                "note_en": note_en,
            }
        )
    fests.sort(key=lambda f: (f["year"] or 0, f["slug"]))

    tags = {}
    tags_path = config.OUT_DIR / "tags.json"
    if tags_path.exists():
        raw = json.loads(tags_path.read_text(encoding="utf-8"))
        tags = {str(k): v for k, v in raw.items() if v}
    extra_tags = config.OUT_DIR / "nextfest" / "_tags_extra.json"
    if extra_tags.exists():
        for tid, name in json.loads(extra_tags.read_text(encoding="utf-8")).items():
            tags.setdefault(str(tid), name)

    # База для долей тегов. Когда фасеты пришли готовыми из Steam (XHR/живой
    # эндпоинт), знаменатель — весь состав. Когда фасеты посчитаны по тегам игр
    # (2021 и реконструкции), знаменатель — только игры с известными тегами.
    tag_basis: dict[str, int] = collections.Counter()
    games_path = config.OUT_DIR / "nextfest_games.jsonl"
    if games_path.exists():
        for line in games_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("tags"):
                tag_basis[rec["fest"]] += 1
    for f in fests:
        f["tag_basis"] = tag_basis.get(f["slug"]) if f.get("facets_from") == "games" else None

    tag_counts: dict[str, dict[str, int]] = collections.defaultdict(dict)
    facets_path = config.OUT_DIR / "nextfest_tag_facets.jsonl"
    if facets_path.exists():
        for line in facets_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            tag_counts[rec["fest"]][str(rec["tagid"])] = rec["games"]

    (SITE_DATA / "fests.json").write_text(
        json.dumps(fests, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (SITE_DATA / "tags.json").write_text(
        json.dumps(tags, ensure_ascii=False), encoding="utf-8"
    )
    (SITE_DATA / "tag_counts.json").write_text(
        json.dumps(tag_counts, ensure_ascii=False), encoding="utf-8"
    )

    # пики CCU по демо (данные копятся во время фестиваля)
    ccu_path = config.OUT_DIR / "nextfest" / "oct2026_demo_ccu.jsonl"
    map_path = config.OUT_DIR / "nextfest" / "oct2026_demo_map.jsonl"
    demo_to_base: dict[str, int] = {}
    if map_path.exists():
        for line in map_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("demo_appid"):
                demo_to_base[str(rec["demo_appid"])] = int(rec["appid"])

    peaks: dict[int, int] = {}
    samples = 0
    if ccu_path.exists():
        for line in ccu_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # последняя строка может быть недописана: поллер пишет в файл
                # параллельно со сборкой
                continue
            samples += 1
            appid = int(rec["appid"])
            peaks[appid] = max(peaks.get(appid, 0), int(rec["players"]))

    # названия игр: appid состава + appid демо
    names = resolve_names()
    wanted: set[int] = set()
    games_path = config.OUT_DIR / "nextfest_games.jsonl"
    if games_path.exists():
        for line in games_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                wanted.add(int(json.loads(line)["appid"]))
    wanted |= {int(k) for k in demo_to_base}
    wanted |= set(peaks)
    names_out = {str(a): names.get(a, "") for a in wanted if names.get(a)}

    # все демо с данными, а не только верхушка: сайт должен уметь искать
    # и сортировать по всему списку, а не показывать топ-20
    ranked = sorted(peaks.items(), key=lambda kv: -kv[1])
    ccu_out = [
        {
            "demo_appid": appid,
            "base_appid": demo_to_base.get(str(appid)),
            "name": names.get(demo_to_base.get(str(appid), 0), "") or names.get(appid, ""),
            "peak": peak,
        }
        for appid, peak in ranked
    ]

    values = sorted(v for v in peaks.values() if v > 0)
    edges = [0, 1, 10, 50, 100, 500, 1000, 5000]
    hist = []
    for lo, hi in zip(edges, edges[1:]):
        hist.append(
            {
                "from": lo,
                "to": hi,
                "games": sum(1 for v in peaks.values() if (v > lo if lo else v == 0) and v <= hi),
            }
        )
    hist.append({"from": edges[-1], "to": None,
                 "games": sum(1 for v in peaks.values() if v > edges[-1])})
    stats = {
        "samples": samples,
        "games": len(peaks),
        "sum_peak": sum(peaks.values()),
        "median": values[len(values) // 2] if values else 0,
        "p90": values[int(len(values) * 0.9)] if values else 0,
        "ge100": sum(1 for v in values if v >= 100),
        "ge1000": sum(1 for v in values if v >= 1000),
        "hist": hist,
    }

    (SITE_DATA / "names.json").write_text(
        json.dumps(names_out, ensure_ascii=False), encoding="utf-8"
    )

    # полная выгрузка: сайт показывает топ и таблицу, но данные не должны
    # упираться в топ — отдаём весь список одним CSV
    import csv as _csv

    with (SITE_DATA / "ccu.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = _csv.writer(fh)
        writer.writerow(["rank", "name", "demo_appid", "base_appid", "peak_players"])
        for i, row in enumerate(ccu_out, 1):
            writer.writerow(
                [i, row["name"], row["demo_appid"], row["base_appid"] or "", row["peak"]]
            )
    (SITE_DATA / "ccu.json").write_text(
        json.dumps(
            {
                "slug": "oct2026",
                "samples": samples,
                "games": len(peaks),
                "stats": stats,
                "top": ccu_out,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"изданий: {len(fests)}, тегов: {len(tags)}, "
          f"изданий с гистограммой: {len(tag_counts)}, замеров CCU: {samples}, "
          f"названий: {len(names_out)}, демо в CCU: {len(ccu_out)}")
    print("папка:", SITE_DATA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
