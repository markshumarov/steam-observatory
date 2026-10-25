"""Разведка: что лежит в архивных страницах и как грузится список участников.

A) сканирует кэш загруженных HTML-страниц Next Fest на ключевые паттерны;
B) скачивает JS-бандлы живой страницы и ищет в них имена эндпоинтов.

Запуск: python scripts/probe_pages.py
"""

from __future__ import annotations

import html as H
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.http import get_text  # noqa: E402

KEYS = [
    "ajax", "saleaction", "salepage", "strContentHubType", "saletag", "clanAccountID",
    "appid", "data-ds-appid", "LoadMore", "load_more", "NextFest", "nextfest",
    "g_rg", "SaleSection", "sale_sections", "tagged_items", "infinite",
]

print("=== A. кэш HTML-страниц ===")
for f in sorted(config.CACHE_DIR.glob("*.html")):
    text = f.read_text(encoding="utf-8", errors="replace")
    print(f"\n-- {f.name}  {len(text)} байт")
    hits = {k: text.count(k) for k in KEYS if text.count(k)}
    print("   ", hits)
    for kw in ("saleaction", "ajax", "salepage", "sale_sections"):
        i = text.find(kw)
        if i >= 0:
            print(f"    [{kw}] ...{text[max(0, i - 100):i + 220]!r}...")

print("\n=== B. JS-бандлы живой страницы ===")
live = None
for f in config.CACHE_DIR.glob("*.html"):
    t = f.read_text(encoding="utf-8", errors="replace")
    if "Next Fest October 2026" in t:
        live = t
        break
if live is None:
    print("живая страница не найдена в кэше — сначала запустите fetch_live.py")
    raise SystemExit(0)

srcs = [H.unescape(s) for s in re.findall(r'<script[^>]+src="([^"]+)"', live)]
srcs = [s for s in srcs if "steamstatic" in s]
print(f"бандлов: {len(srcs)}")
for url in srcs:
    try:
        body = get_text(url, suffix=".js")
    except Exception as exc:  # noqa: BLE001
        print("  ERR", url[-40:], exc)
        continue
    hits = sorted(set(re.findall(r"[A-Za-z_/]*ajax[A-Za-z_/]*", body))) + sorted(
        set(re.findall(r"[A-Za-z_/]*salepage[A-Za-z_/]*", body))
    )
    if hits:
        print("  ", url.split("/")[-1].split("?")[0], hits[:20])
