"""Полное описание выбранных инструментов PlayRecon (из кэша tools/list)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "data" / "cache" / "playrecon_tools.json"
OUT = ROOT / "data" / "cache" / "pr_tool_docs.txt"

names = sys.argv[1:] or ["nextfest_live"]
tools = {t["name"]: t for t in json.loads(TOOLS.read_text(encoding="utf-8"))}
chunks: list[str] = []
for name in names:
    t = tools.get(name)
    if not t:
        chunks.append(f"--- {name}: НЕТ ТАКОГО ИНСТРУМЕНТА")
        continue
    chunks.append("=" * 100)
    chunks.append(f"{name}")
    chunks.append(json.dumps(t.get("inputSchema"), ensure_ascii=False, indent=1))
    chunks.append("-" * 100)
    chunks.append(t.get("description") or "")

OUT.write_text("\n".join(chunks), encoding="utf-8")
print(f"док: {OUT} ({OUT.stat().st_size} байт)")
