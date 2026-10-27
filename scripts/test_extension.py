"""Проверка расширения на реальном DOM страницы PlayRecon.

Берём сохранённый снимок страницы фестиваля, подключаем content.js и проверяем:
колонка появилась, значения посчитаны, сортировка по клику работает.

Запуск: python scripts/test_extension.py
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from sobs import config  # noqa: E402

ROOT = config.ROOT
SNAPSHOT = ROOT / "data" / "cache" / "playrecon_fest_dom.html"
EXT = ROOT / "extensions" / "playrecon-wishlist-gain" / "content.js"
PORT = 8797
REPORT = ROOT / "data" / "cache" / "ext_test.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(str(text))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()

errors: list[str] = []
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    say(f"{'OK  ' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1700, "height": 1100})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "console",
            # 404 на ассеты снимка — это не ошибка расширения
            lambda m: errors.append(f"{m.type}: {m.text}")
            if m.type == "error" and "Failed to load resource" not in m.text
            else None,
        )
        page.goto(f"http://127.0.0.1:{PORT}/data/cache/{SNAPSHOT.name}",
                  wait_until="domcontentloaded", timeout=120000)
        page.wait_for_selector("table tbody tr", timeout=60000)
        page.add_script_tag(path=str(EXT))
        page.wait_for_timeout(1500)

        check("колонка в шапке появилась",
              page.eval_on_selector_all("th[data-pr-gain]", "e => e.length") == 1)
        cells = page.eval_on_selector_all("td.pr-gain", "e => e.length")
        check("ячейки добавлены в строки", cells > 500, f"ячеек={cells}")

        first = page.eval_on_selector("td.pr-gain", "e => e.textContent.trim()")
        check("первая строка посчитана", first.startswith("+"), f"значение={first}")

        title = page.eval_on_selector("td.pr-gain", "e => e.title")
        check("в подсказке есть оговорка о погрешности", "±20–30%" in title,
              title.splitlines()[0][:60])

        # строка с оценкой через запятую (≈53,800) раньше читалась как «53» — проверяем отдельно
        comma_row = page.evaluate(
            """() => {
                const tr = Array.from(document.querySelectorAll('tbody tr'))
                    .find(r => (r.textContent || '').includes('Rip It!'));
                if (!tr) return null;
                const cell = tr.querySelector('td.pr-gain');
                return { text: cell ? cell.textContent.trim() : null,
                         gain: cell ? Number(cell.dataset.gain) : null,
                         wl: Array.from(tr.querySelectorAll('td,th')).slice(-2, -1)[0]?.textContent.trim() };
            }"""
        )
        check("строка с запятой в оценке посчитана верно",
              bool(comma_row) and (comma_row.get("gain") or 0) > 20000,
              str(comma_row))

        # сортировка: клик по заголовку поднимает наверх максимальный прирост
        # (page.click может перехватываться липкой шапкой — жмём через JS)
        page.eval_on_selector("th[data-pr-gain]", "el => el.click()")
        page.wait_for_timeout(500)
        top = page.eval_on_selector("tbody tr td.pr-gain", "e => e.dataset.gain")
        best = page.eval_on_selector_all(
            "tbody tr td.pr-gain",
            "els => els.reduce((m, e) => Math.max(m, Number(e.dataset.gain) || -1), -1)")
        check("сортировка по убыванию работает", int(top) == best, f"верх={top}, максимум={best}")

        page.eval_on_selector("th[data-pr-gain]", "el => el.click()")
        page.wait_for_timeout(500)
        worst = page.eval_on_selector("tbody tr td.pr-gain", "e => e.dataset.gain")
        check("повторный клик сортирует по возрастанию", int(worst) < best,
              f"низ={worst}, максимум={best}")

        shot = config.OUT_DIR / "extension_check.png"
        page.screenshot(path=str(shot))
        say(f"скриншот: {shot.name} {shot.stat().st_size} байт")
        browser.close()
except Exception:  # noqa: BLE001 — отчёт нужен даже при падении
    lines.append(traceback.format_exc())

say(f"ошибок в консоли: {len(errors)}")
for e in errors[:5]:
    say(f"   {e}")
say(f"провалено проверок: {len(failures)}")

REPORT.write_text("\n".join(lines), encoding="utf-8")
print(f"отчёт: {REPORT}")
sys.exit(1 if failures or "Traceback" in "\n".join(lines) else 0)

