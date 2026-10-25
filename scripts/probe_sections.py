"""Извлечь все серверно-отрендеренные блоки `data-browser_*` (массивы appids).

Запуск: python scripts/probe_sections.py <файл|live>
"""

from __future__ import annotations

import collections
import html as H
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402

ATTR_RE = re.compile(r'data-([A-Za-z0-9_*.~-]+)="([^"]{20,})"')

target = sys.argv[1] if len(sys.argv) > 1 else "live"
if target == "live":
    path = None
    for f in sorted(config.CACHE_DIR.glob("*"), key=lambda p: -p.stat().st_size):
        if f.stat().st_size < 2_000_000:
            continue
        if "sale_nextfest_october_2026" in f.read_text(encoding="utf-8", errors="replace"):
            path = f
            break
else:
    path = Path(target)

if path is None or not path.exists():
    print("файл не найден")
    raise SystemExit(1)

text = path.read_text(encoding="utf-8", errors="replace")
print(f"файл: {path.name}  {len(text)} байт")
print("data-browser_*:", len(re.findall(r"data-browser_", text)))
print("&quot;appids&quot;:", text.count("&quot;appids&quot;"))
print("data-attributes:", len(ATTR_RE.findall(text)))

all_ids: set[int] = set()
sections = collections.Counter()
for name, raw in ATTR_RE.findall(text):
    if "appids" not in raw:
        continue
    try:
        obj = json.loads(H.unescape(raw))
    except json.JSONDecodeError:
        continue
    ids: list[int] = []
    if isinstance(obj, dict):
        ids = [int(a) for a in obj.get("appids", []) if str(a).isdigit()]
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and str(item.get("appid", "")).isdigit():
                ids.append(int(item["appid"]))
            elif isinstance(item, int):
                ids.append(item)
    if not ids:
        continue
    all_ids.update(ids)
    sections[name] += len(ids)

print(f"\nсекций с appids: {len(sections)}")
for name, n in sections.most_common(15):
    print(f"  {n:>5}  {name[:90]}")
print(f"\nуникальных appid всего: {len(all_ids)}")
