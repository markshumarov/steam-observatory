"""Диагностика всплывающей подсказки Plot: из чего она сделана и какие стили наследует."""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cache" / "tip_probe.txt"
PORT = 8798

try:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
except Exception:  # noqa: BLE001
    pass


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(ROOT / "site")))
threading.Thread(target=srv.serve_forever, daemon=True).start()

lines: list[str] = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="load", timeout=60000)
    page.wait_for_selector("#chart-editions svg", timeout=30000)
    page.wait_for_timeout(1200)

    # наводим курсор на первый столбец диаграммы изданий
    bar = page.query_selector("#chart-editions svg rect")
    bar.hover()
    page.wait_for_timeout(600)

    info = page.evaluate(
        """() => {
            const nodes = Array.from(document.querySelectorAll('[aria-label]'))
                .filter(el => /tip/i.test(el.getAttribute('aria-label') || ''));
            const dump = (el) => {
                const cs = getComputedStyle(el);
                return {
                    tag: el.tagName,
                    fill: cs.fill, stroke: cs.stroke, color: cs.color,
                    opacity: cs.opacity, filter: cs.filter,
                    attrFill: el.getAttribute('fill'), attrStroke: el.getAttribute('stroke'),
                };
            };
            return nodes.map(el => ({
                tag: el.tagName,
                aria: el.getAttribute('aria-label'),
                self: dump(el),
                children: Array.from(el.children).map(dump),
                html: el.outerHTML.slice(0, 500),
            }));
        }"""
    )
    lines.append(f"элементов-подсказок: {len(info)}")
    for el in info:
        lines.append("")
        lines.append(f"<{el['tag']} aria={el['aria']!r}> self: {el['self']}")
        for child in el["children"]:
            lines.append(f"  <{child['tag']}> fill={child['fill']} stroke={child['stroke']} "
                         f"attrFill={child['attrFill']}")
        lines.append(f"  html={el['html'][:400]}")

    shot = ROOT / "data" / "processed" / "tip_probe.png"
    page.screenshot(path=str(shot))
    lines.append("")
    lines.append(f"скриншот: {shot.name}")
    browser.close()

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {OUT}")
