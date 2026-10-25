"""Первый числовой отчёт: насыщенность тегов в издании фестиваля.

Показывает топ тегов по числу участников, их долю и — если есть данные другого
издания — динамику. Это заготовка «цифры первичны»: таблица вместо статьи.

Запуск: python scripts/report_tags.py [slug] [--compare other-slug]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.fests import by_slug  # noqa: E402

BASE = config.OUT_DIR / "nextfest"


def load_facets(slug: str) -> tuple[dict[int, int], int, str]:
    """Агрегаты по тегам, число игр и имя источника.

    Выбираем тот же вариант состава, что и `build_dataset.py`: ближайший
    к контрольному числу участников издания.
    """
    try:
        expected = by_slug(slug).expected
    except KeyError:
        expected = None

    paths = [BASE / f"{slug}_lineup.json", *sorted(BASE.glob(f"{slug}_*_lineup_ajax.json"))]
    best: tuple[float, dict[int, int], int, str] | None = None
    for path in paths:
        if not path.exists():
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        facets = {int(k): int(v) for k, v in (rec.get("tag_facet_counts") or {}).items()}
        if not facets:
            continue
        n = len(rec.get("appids") or [])
        diff = abs(n - expected) / expected if expected else 0.0
        if best is None or diff < best[0]:
            best = (diff, facets, n, path.name)

    if best is None:
        return {}, 0, ""
    return best[1], best[2], best[3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?", default="oct2026")
    ap.add_argument("--compare", help="второе издание для сравнения")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    tags_path = BASE / "steam_tags.json"
    names = {}
    if tags_path.exists():
        for item in json.loads(tags_path.read_text(encoding="utf-8")):
            if isinstance(item, dict) and "tagid" in item:
                names[int(item["tagid"])] = item.get("name", "")

    facets, n_games, src = load_facets(args.slug)
    if not facets:
        print(f"нет данных по тегам для {args.slug}")
        return 1

    other, other_games, other_src = load_facets(args.compare) if args.compare else ({}, 0, "")

    print(f"Издание {args.slug}: игр {n_games}, тегов в гистограмме {len(facets)}  [{src}]")
    if other:
        print(f"Сравнение {args.compare}: игр {other_games}  [{other_src}]")
    print()
    header = f"{'#':>3} {'тег':28} {'игр':>6} {'доля':>7}"
    if other:
        header += f"  {'доля(' + str(args.compare) + ')':>12} {'изм.,пп':>9}"
    print(header)
    print("-" * len(header))

    for i, (tid, n) in enumerate(sorted(facets.items(), key=lambda kv: -kv[1])[: args.top], 1):
        name = names.get(tid) or f"tagid {tid}"
        share = 100 * n / max(n_games, 1)
        line = f"{i:>3} {name[:28]:28} {n:>6} {share:>6.1f}%"
        if other:
            o = other.get(tid, 0)
            share_other = 100 * o / max(other_games, 1)
            line += f"  {share_other:>11.1f}% {share - share_other:>+8.1f}"
        print(line)

    print(f"\nвсего тегов: {len(facets)}; сумма вхождений: {sum(facets.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
