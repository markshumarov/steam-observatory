"""Проверка эндпоинта динамической выдачи игр страницы распродажи.

Гипотеза: `saleaction/ajaxgetsaledynamicappquery` принимает POST и/или требует
корректной пары (saletag, clanAccountID). Пробуем комбинации с сессией,
полученной со страницы фестиваля.

Запуск: python scripts/probe_endpoint.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests  # noqa: E402

from sobs import config  # noqa: E402

URL = "https://store.steampowered.com/saleaction/ajaxgetsaledynamicappquery"
CLAN = "39049601"

s = requests.Session()
s.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": config.NEXTFEST_PAGE,
        "X-Requested-With": "XMLHttpRequest",
    }
)
r = s.get(config.NEXTFEST_PAGE, timeout=60)
print("прогрев сессии:", r.status_code, "cookies:", list(s.cookies.keys()))

base = {"cc": "us", "l": "english", "strTagFilter": "", "nCount": "100", "start": "0"}

combos = [
    {"strContentHubType": "sale", "saletag": CLAN, "clanAccountID": CLAN},
    {"strContentHubType": "nextfest", "saletag": CLAN, "clanAccountID": CLAN},
    {"strContentHubType": "sale", "saletag": "nextfest", "clanAccountID": CLAN},
    {"strContentHubType": "sale", "saletag": "102", "clanAccountID": CLAN},
    {"strContentHubType": "nextfest", "saletag": "nextfest_october_2026", "clanAccountID": CLAN},
    {"strContentHubType": "sale", "saletag": CLAN, "clanAccountID": CLAN, "bShuffle": "false",
     "bFilterUnowned": "false", "strTagFilter": ""},
]

for combo in combos:
    data = {**base, **combo}
    for method in ("POST", "GET"):
        try:
            if method == "POST":
                resp = s.post(URL, data=data, timeout=60)
            else:
                resp = s.get(URL, params=data, timeout=60)
            body = resp.text[:160].replace("\n", " ")
        except Exception as exc:  # noqa: BLE001
            body = f"ERR {exc}"
            resp = None
        code = resp.status_code if resp is not None else "-"
        print(f"{method:4} {code} {combo.get('strContentHubType'):9} saletag={combo.get('saletag'):22} -> {body}")
