"""Слить замеры CCU из двух источников в один файл (без перезаписи).

Локальный поллер остановлен, но в его файле есть замеры, которых нет на remote,
и наоборот. Скрипт читает версию origin/main, дописывает в конец локального файла
недостающие строки (уникальность по паре appid + ts) и печатает итог.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "processed" / "nextfest" / "oct2026_demo_ccu.jsonl"


def key(line: str) -> str:
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return line
    return f"{rec.get('appid')}|{rec.get('ts') or rec.get('timestamp')}"


remote = subprocess.run(
    ["git", "show", f"origin/main:data/processed/nextfest/{TARGET.name}"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout.splitlines()

local = TARGET.read_text(encoding="utf-8").splitlines()
have = {key(line) for line in local if line.strip()}
extra = [line for line in remote if line.strip() and key(line) not in have]

print(f"локально: {len(local)}, на remote: {len(remote)}, новых с remote: {len(extra)}")
if extra:
    with TARGET.open("a", encoding="utf-8") as fh:
        for line in extra:
            fh.write(line + "\n")
print(f"итого строк: {len(TARGET.read_text(encoding='utf-8').splitlines())}")
