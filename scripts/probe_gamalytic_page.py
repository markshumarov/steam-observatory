"""Что показывает страница Gamalytic: ищем вишлисты в отрендеренном DOM и в сети.

Запуск: python scripts/probe_gamalytic_page.py [appid]
Выход:  data/cache/probe_gamalytic_page.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

APPID = int(sys.argv[1]) if len(sys.argv) > 1 else 2295170
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cache" / "probe_gamalytic_page.txt"
seen: list[str] = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})

    def on_response(resp):
        ctype = (resp.headers or {}).get("content-type", "")
        if "json" in ctype and len(seen) < 30:
            seen.append(f"{resp.status} {resp.url[:150]}")

    page.on("response", on_response)
    page.goto(f"https://gamalytic.com/game/{APPID}", wait_until="domcontentloaded",
              timeout=90000)
    page.wait_for_timeout(9000)
    text = page.inner_text("body")
    browser.close()

lines = [
    ln.strip()
    for ln in text.splitlines()
    if "wishlist" in ln.lower() or re.search(r"\b\d{2,4}\s*K\b", ln)
]
OUT.write_text(
    "\n".join(["--- строки про вишлисты:"] + lines[:25] + ["--- json-ответы:"] + seen),
    encoding="utf-8",
)
print("\n".join(lines[:12]))
print(f"json-ответов: {len(seen)}")
