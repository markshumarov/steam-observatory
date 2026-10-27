"""Снять таблицу фестиваля PlayRecon из отрендеренной страницы.

RSC-поток содержит React-дерево, поэтому проще открыть страницу в браузере,
дождаться таблицы и снять её DOM. Заодно слушаем сетевые ответы: если у страницы
есть JSON-API, дальше можно брать данные прямо из него.

Запуск: python scripts/scrape_playrecon_fest_dom.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
URL = "https://app.playrecon.com/fests/nextfest/autumn-2026?top=1000&sort=players&dir=desc"

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
    out = CACHE / "playrecon_fest_table.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for cells in rows:
            fh.write(json.dumps(cells, ensure_ascii=False) + "\n")
    print(f"строк снято: {len(rows)} -> {out.name}")

    # агрегаты по жанрам (первая таблица) — тоже полезны
    genres = page.eval_on_selector_all(
        "table:nth-of-type(1) tbody tr",
        "els => els.map(tr => Array.from(tr.querySelectorAll('td,th')).map(c => c.textContent.trim()))",
    )
    (CACHE / "playrecon_fest_genres.json").write_text(
        json.dumps(genres, ensure_ascii=False, indent=1), encoding="utf-8")

    print("JSON-ответы страницы:")
    for r in responses:
        print("  ", r["status"], r["url"][:140])
    browser.close()

