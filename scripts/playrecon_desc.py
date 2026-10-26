"""Печатать полные описания инструментов PlayRecon (без схем) в файл."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tools = {t["name"]: t for t in json.loads(
    (ROOT / "data" / "cache" / "playrecon_tools.json").read_text(encoding="utf-8"))}
names = sys.argv[1:]
out = ROOT / "data" / "cache" / "pr_desc.txt"
chunks: list[str] = []
for name in names:
    t = tools.get(name)
    chunks.append("=" * 90)
    chunks.append(name)
    chunks.append(t.get("description") if t else "НЕТ ИНСТРУМЕНТА")
out.write_text("\n".join(chunks), encoding="utf-8")
print(f"описания: {out}")
