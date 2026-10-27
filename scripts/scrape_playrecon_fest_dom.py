"""Снять таблицу фестиваля PlayRecon из отрендеренной страницы.

RSC-поток содержит React-дерево, поэтому проще открыть страницу в браузере,
дождаться таблицы и снять её DOM. Заодно слушаем сетевые ответы: если у страницы
есть JSON-API, дальше можно брать данные прямо из него.

Страница принимает параметры: ?top=N&sort=players|wishlists&dir=desc.
Поэтому «топ-1000 по игрокам» и «весь состав фестиваля» — это один и тот же
публичный HTML, без обращений к MCP и без расхода CU.

Запуск: python scripts/scrape_playrecon_fest_dom.py
        python scripts/scrape_playrecon_fest_dom.py --top 8000 --out fest_all
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
DEFAULT_URL = "https://app.playrecon.com/fests/nextfest/autumn-2026?top=1000&sort=players&dir=desc"

ap = argparse.ArgumentParser()
ap.add_argument("--url", default=None, help="полный URL страницы фестиваля")
ap.add_argument("--top", type=int, default=None, help="сколько строк просить у страницы")
ap.add_argument("--sort", default=None, help="players | wishlists")
ap.add_argument("--dir", default=None, help="desc | asc")
ap.add_argument("--out", default="playrecon_fest_table", help="имя файла без .jsonl")
ap.add_argument("--genres-out", default="playrecon_fest_genres")
args = ap.parse_args()

URL = args.url or DEFAULT_URL
if args.top or args.sort or args.dir:
    base = URL.split("?")[0]
    params = {
        "top": args.top or 1000,
        "sort": args.sort or "players",
        "dir": args.dir or "desc",
    }
    URL = base + "?" + "&".join(f"{k}={v}" for k, v in params.items())

responses: list[dict] = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1200})

    def on_response(resp):
        ctype = (resp.headers or {}).get("content-type", "")
        if "json" in ctype and len(responses) < 40:
            responses.append({"url": resp.url, "status": resp.status, "type": ctype})

    page.on("response", on_response)
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(9000)

    html = page.content()
    (CACHE / "playrecon_fest_dom.html").write_text(html, encoding="utf-8")

    # главная таблица — та, где больше всего строк (остальные — агрегаты по жанрам)
    rows = page.eval_on_selector_all(
        "table",
        """els => {
            const t = els.slice().sort((a, b) =>
                b.querySelectorAll('tbody tr').length - a.querySelectorAll('tbody tr').length)[0];
            if (!t) return [];
            return Array.from(t.querySelectorAll('tbody tr'))
                .map(tr => Array.from(tr.querySelectorAll('td,th'))
                    .map(td => td.textContent.trim()));
        }""",
    )
    out = CACHE / f"{args.out}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for cells in rows:
            fh.write(json.dumps(cells, ensure_ascii=False) + "\n")
    print(f"строк снято: {len(rows)} -> {out.name}")

    # агрегаты по жанрам (первая таблица) — тоже полезны
    genres = page.eval_on_selector_all(
        "table:nth-of-type(1) tbody tr",
        "els => els.map(tr => Array.from(tr.querySelectorAll('td,th')).map(c => c.textContent.trim()))",
    )
    (CACHE / f"{args.genres_out}.json").write_text(
        json.dumps(genres, ensure_ascii=False, indent=1), encoding="utf-8")

    print("JSON-ответы страницы:")
    for r in responses:
        print("  ", r["status"], r["url"][:140])
    browser.close()

