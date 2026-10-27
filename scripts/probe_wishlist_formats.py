"""Диагностика: какие форматы у колонки Wishlists и где парсер ошибается."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "cache" / "playrecon_fest_table.jsonl"
OUT = ROOT / "data" / "cache" / "wl_formats.txt"

WL_RE = re.compile(
    r"#([\d\s,]+)(?:([\u25b2\u25bc])\s*([\d\s,]+))?\s*\u2248\s*([\d.,]+)\s*([KM]?)")

lines: list[str] = []
cells: list[str] = []
for line in TABLE.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if len(row) >= 8:
        cells.append(row[-1])

lines.append(f"строк: {len(cells)}")
shapes: collections.Counter = collections.Counter()
bad: list[str] = []
for cell in cells:
    shape = re.sub(r"\d+", "N", cell).replace("N,NNN", "N,NNN")
    shapes[shape] += 1
    m = WL_RE.search(cell)
    if not m:
        continue
    tail = cell[m.end():].strip()
    # если после совпадения остались цифры или запятая — значит оценка разобрана не полностью
    if tail[:1].isdigit() or tail.startswith(","):
        bad.append(cell)

lines.append("\nсамые частые формы:")
for shape, n in shapes.most_common(12):
    lines.append(f"  {n:5}  {shape}")

lines.append(f"\nнеполный разбор оценки: {len(bad)}")
for cell in bad[:10]:
    lines.append(f"  {cell}")

# распределение оценок по нашему шаблону
est_values: list[int] = []
for cell in cells:
    m = WL_RE.search(cell)
    if not m:
        continue
    mult = {"K": 1_000, "M": 1_000_000}.get(m.group(5) or "", 1)
    est_values.append(int(float(m.group(4).replace(",", "")) * mult))
small = [v for v in est_values if v < 10_000]
lines.append(f"\nоценок всего: {len(est_values)}, из них меньше 10 000: {len(small)} (похоже на обрезанные)")
lines.append(f"примеры мелких: {sorted(small)[:15]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {OUT}")
