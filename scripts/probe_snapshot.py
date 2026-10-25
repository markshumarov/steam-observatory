"""Скачать конкретный снапшот и показать статистику разбора.

Запуск: python scripts/probe_snapshot.py <url-снапшота>
Пример: python scripts/probe_snapshot.py http://web.archive.org/web/20211104145926id_/https://store.steampowered.com/sale/nextfest
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs.http import get_text  # noqa: E402
from sobs.parse import extract_games, page_title  # noqa: E402

url = sys.argv[1]
html = get_text(url, suffix=".html")
print(f"{len(html)} байт | заголовок: {page_title(html)!r}")

games, strategy = extract_games(html)
print(f"объектов: {len(games)}, стратегия: {strategy}")

groups = collections.Counter(tuple(sorted(g.keys()))[:8] for g in games)
for sig, n in groups.most_common(5):
    print(f"  [{n}] {', '.join(sig)}")

valid = [
    g
    for g in games
    if (g.get("title") or g.get("name"))
    and (g.get("tags") or g.get("capsule") or g.get("tiny_capsule") or g.get("main_capsule"))
]
print(f"валидных карточек: {len(valid)}")
if valid:
    print("пример:", json.dumps(valid[0], ensure_ascii=False)[:600])
