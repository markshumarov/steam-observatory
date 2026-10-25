"""Замер скорости публичного API Steam (CCU): 12 запросов подряд.

Запуск: python scripts/probe_ccu_speed.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs.sources.steam import UA  # noqa: E402

IDS = [4690300, 5040820, 4754730, 730, 620, 570, 440, 1243310, 2107550, 2322180, 1, 70]
s = requests.Session()
s.headers.update({"User-Agent": UA})

ok = err = 0
t0 = time.time()
for appid in IDS:
    t = time.time()
    try:
        r = s.get(
            "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
            params={"appid": appid},
            timeout=20,
        )
        dt = time.time() - t
        body = r.text[:60].replace("\n", " ")
        print(f"{appid:>9}  {r.status_code}  {dt:5.2f}s  {body}")
        ok += 1 if r.status_code == 200 else 0
        err += 0 if r.status_code == 200 else 1
    except Exception as exc:  # noqa: BLE001
        print(f"{appid:>9}  ERR  {time.time() - t:5.2f}s  {exc}")
        err += 1

print(f"\nитого: ok={ok} err={err}, {time.time() - t0:.1f}s на {len(IDS)} запросов")
