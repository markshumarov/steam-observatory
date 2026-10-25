"""Разведка живой страницы Next Fest через Playwright + системный Edge.

1. открывает страницу фестиваля;
2. логирует все JSON/XHR-ответы (ищем эндпоинт полного списка);
3. прокручивает страницу, собирая appid из ссылок /app/<id>/;
4. пишет результат в data/processed/probe_live.json.

Запуск: python scripts/probe_playwright.py [url] [max_scrolls]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from sobs import config  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else config.NEXTFEST_PAGE
MAX_SCROLLS = int(sys.argv[2]) if len(sys.argv) > 2 else 40
OUT = config.OUT_DIR / "probe_live.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    xhr: list[tuple[str, int, str]] = []
    appids: set[int] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1500, "height": 1200}, locale="en-US")
        page = ctx.new_page()

        def on_response(resp) -> None:
            try:
                ct = (resp.headers or {}).get("content-type", "")
                url = resp.url
                if "json" in ct or "saleaction" in url or "salepage" in url or "ajax" in url:
                    xhr.append((url, resp.status, ct))
            except Exception:  # noqa: BLE001
                pass

        page.on("response", on_response)
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        js_hrefs = (
            "() => Array.from(document.querySelectorAll('a'), "
            "a => a.getAttribute('href') || '').join('|')"
        )

        for i in range(MAX_SCROLLS):
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(700)
            hrefs = page.evaluate(js_hrefs)
            found = {int(x) for x in re.findall(r"/app/(\d+)/", hrefs)}
            new = found - appids
            appids |= found
            if i % 5 == 0 or new:
                log(f"scroll {i}: +{len(new)} (всего appid {len(appids)})")
            if len(appids) > 7400:
                break

        html = page.content()
        (config.CACHE_DIR / "live_rendered.html").write_text(html, encoding="utf-8")
        browser.close()

    payload = {
        "url": URL,
        "n_appids": len(appids),
        "appids": sorted(appids),
        "xhr": [{"url": u, "status": s, "ct": c} for u, s, c in sorted(set(xhr))],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"ИТОГО appid: {len(appids)}; XHR-запросов: {len(payload['xhr'])}; файл: {OUT}")


main()
