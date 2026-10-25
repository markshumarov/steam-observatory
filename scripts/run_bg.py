"""Запустить скрипт в фоне (обход лимита времени на команду) и писать лог в файл.

Запуск: python scripts/run_bg.py scripts/probe_playwright.py [аргументы]
Лог:    data/cache/bg.log
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = sys.argv[1]
extra = sys.argv[2:]

stem = Path(script).stem
log_path = ROOT / "data" / "cache" / f"bg_{stem}.log"
log_path.parent.mkdir(parents=True, exist_ok=True)

log = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 — файл живёт до конца процесса
proc = subprocess.Popen(
    [sys.executable, script, *extra],
    cwd=str(ROOT),
    stdout=log,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
(ROOT / "data" / "cache" / "bg.pid").write_text(str(proc.pid), encoding="utf-8")
print(f"запущено: pid={proc.pid}, лог: {log_path}")
