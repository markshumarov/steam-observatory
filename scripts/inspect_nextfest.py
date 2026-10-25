"""Инспекция структуры архивной страницы Next Fest.

Показывает, какие поля есть у извлечённых объектов и как отличить участников
фестиваля от «прочих» игр на странице.

Запуск: python scripts/inspect_nextfest.py [slug]
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.parse import extract_games  # noqa: E402

slug = sys.argv[1] if len(sys.argv) > 1 else "jun2023"
files = sorted((config.RAW_DIR / "nextfest").glob(f"{slug}_*.html"))
if not files:
    print("нет сырых страниц для", slug)
    raise SystemExit(1)

path = files[-1]
text = path.read_text(encoding="utf-8", errors="replace")
print(f"файл: {path.name}  {len(text)} байт")

games, strategy = extract_games(text)
print(f"извлечено объектов: {len(games)}, стратегия: {strategy}")

# Группируем объекты по «подписи» ключей: так видно, какие структуры есть на странице.
groups: dict[tuple, list[dict]] = collections.defaultdict(list)
for g in games:
    sig = tuple(sorted(g.keys()))[:10]
    groups[sig].append(g)

print(f"\nгрупп по подписи ключей: {len(groups)}")
for sig, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:8]:
    print(f"\n  [{len(items)} объектов] ключи: {', '.join(sig)}")
    print("   пример:", json.dumps(items[0], ensure_ascii=False)[:600])

with_tags = sum(1 for g in games if g.get("tags"))
with_title = sum(1 for g in games if g.get("title") or g.get("name"))
print(f"\nс тегами: {with_tags}; с названием: {with_title}")
