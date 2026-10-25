"""Проверка сайта: локальный сервер + рендер в headless-браузере.

Проверяем, что графики действительно отрисовались (SVG/столбцы), таблицы
заполнены, и в консоли нет ошибок. Скриншот сохраняется в data/processed/.

Запуск: python scripts/validate_site.py
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from sobs import config  # noqa: E402

SITE = config.ROOT / "site"
PORT = 8791

# Если передан URL — проверяем развёрнутый сайт, иначе поднимаем локальный сервер.
TARGET = sys.argv[1] if len(sys.argv) > 1 else None


def serve() -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        httpd.serve_forever()


if TARGET is None:
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(0.6)
    URL = f"http://127.0.0.1:{PORT}/"
else:
    URL = TARGET

errors: list[str] = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.on(
        "console",
        lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None,
    )
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(5000)

    counts = {
        "svg": page.eval_on_selector_all("svg", "els => els.length"),
        "столбцов": page.eval_on_selector_all("svg rect", "els => els.length"),
        "точек/линий": page.eval_on_selector_all("svg circle, svg path", "els => els.length"),
        "строк таблиц": page.eval_on_selector_all("table tr", "els => els.length"),
        "чипов тегов": page.eval_on_selector_all(".chip", "els => els.length"),
    }
    for key, value in counts.items():
        print(f"{key}: {value}")
    print("ccu-meta:", page.text_content("#ccu-meta"))
    print("первая строка таблицы изданий:", page.text_content("#table-editions tbody tr"))

    shot = config.OUT_DIR / "site_screenshot.png"
    page.screenshot(path=str(shot), full_page=True)
    print("скриншот:", shot, shot.stat().st_size, "байт")
    browser.close()

print("ошибок в консоли:", len(errors))
for e in errors[:10]:
    print("  ", e)
