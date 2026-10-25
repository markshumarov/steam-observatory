"""Показать контекст ключевых слов в сохранённой странице.

Запуск: python scripts/probe_context.py <файл|live> <ключевое слово> [сколько контекстов]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402

target = sys.argv[1] if len(sys.argv) > 1 else "live"
kw = sys.argv[2] if len(sys.argv) > 2 else "sale_sections"
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 4

if target == "live":
    path = None
    for f in config.CACHE_DIR.glob("*.html"):
        head = f.read_text(encoding="utf-8", errors="replace")[:200000]
        if "sale_vanity_id" in head and f.stat().st_size > 2_000_000:
            path = f
            break
else:
    path = Path(target)

if path is None or not path.exists():
    print("файл не найден")
    raise SystemExit(1)

text = path.read_text(encoding="utf-8", errors="replace")
print(f"файл: {path.name}  {len(text)} байт")
print(f"вхождений {kw!r}: {text.count(kw)}")
for alt in ("u0022", "\\u0022", "&quot;appid", "appid%22", "\\x22"):
    print(f"  альтернативная кодировка {alt!r}: {text.count(alt)}")

pos = -1
for i in range(limit):
    pos = text.find(kw, pos + 1)
    if pos < 0:
        break
    print(f"\n--- контекст #{i + 1} @ {pos}")
    print(repr(text[max(0, pos - 250):pos + 450]))
