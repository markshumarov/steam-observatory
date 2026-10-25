"""Полный конвейер одной командой: сбор -> датасет -> данные сайта.

Запуск:
    python scripts/run_all.py              # всё, включая тяжёлые бэкфиллы Wayback
    python scripts/run_all.py --fast       # без Wayback (только текущее издание + пересборка)
    python scripts/run_all.py --slug oct2026
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(title: str, args: list[str]) -> bool:
    print(f"\n=== {title}: {' '.join(args[1:])}", flush=True)
    started = time.time()
    proc = subprocess.run([PY, *args], cwd=str(ROOT))
    status = "ок" if proc.returncode == 0 else f"ОШИБКА (код {proc.returncode})"
    print(f"--- {title}: {status}, {(time.time() - started):.1f} с", flush=True)
    return proc.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="oct2026")
    ap.add_argument("--fast", action="store_true", help="без бэкфиллов Wayback")
    ap.add_argument("--candidates", type=int, default=8)
    args = ap.parse_args()

    steps: list[tuple[str, list[str]]] = []
    if not args.fast:
        steps += [
            ("составы из Wayback (HTML, 2021)", ["scripts/backfill_nextfest.py", "--candidates", str(args.candidates)]),
            ("составы из Wayback (XHR, 2024+)", ["scripts/backfill_lineup_ajax.py", "--fetch"]),
            # appid-срезы: страницы 2021–2024 отдавали в HTML только часть списка
            ("appid-срезы Wayback (2021–2024)", ["scripts/backfill_ids.py"]),
        ]
    steps += [
        ("состав текущего издания", ["scripts/ingest_nextfest_lineup.py", args.slug]),
        # названия и теги к восстановленным составам: Gamalytic + Steam appdetails
        ("обогащение восстановленных составов", ["scripts/enrich_lineup_ids.py"]),
        ("единый датасет", ["scripts/build_dataset.py"]),
        ("данные сайта", ["scripts/build_site_data.py"]),
        ("отчёт по тегам", ["scripts/report_tags.py", args.slug, "--top", "15"]),
    ]

    failed = [title for title, cmd in steps if not run(title, cmd)]
    print("\n=== итог:", "всё прошло" if not failed else f"сбои: {', '.join(failed)}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
