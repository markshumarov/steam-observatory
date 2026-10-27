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
        check("первая строка посчитана", first.startswith("\U0001f48e"), f"значение={first}")

        header_text = page.eval_on_selector("th[data-pr-gain]", "e => e.textContent.trim()")
        check("колонка называется Wishlist change", header_text.startswith("Wishlist change"),
              header_text)

        tier_first = page.eval_on_selector("td.pr-gain", "e => e.dataset.tier")
        check("медалька соответствует тиру", tier_first == "diamond", f"тир={tier_first}")

        bronze = page.evaluate(
            """() => {
                const cell = Array.from(document.querySelectorAll('td.pr-gain'))
                    .find(c => c.dataset.tier === 'bronze');
                return cell ? { text: cell.textContent.trim(), tier: cell.dataset.tier } : null;
            }"""
        )
        check("у бронзового тира медалька 🥉",
              bool(bronze) and bronze["text"].startswith("\U0001f949"), str(bronze))

        tiers_seen = page.evaluate(
            """() => Array.from(new Set(Array.from(document.querySelectorAll('td.pr-gain'))
                .map(c => c.dataset.tier).filter(Boolean))).sort()"""
        )
        check("в таблице есть все четыре тира", len(tiers_seen) == 4, str(tiers_seen))

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

        # сортировка: клик по заголовку перебирает режимы
        # (обычный page.click может перехватываться липкой шапкой — жмём через JS)
        def click_header():
            page.eval_on_selector("th[data-pr-gain]", "el => el.click()")
            page.wait_for_timeout(500)

        def gains(limit=12):
            return page.eval_on_selector_all(
                "tbody tr td.pr-gain",
                f"els => els.slice(0, {limit}).map(e => e.dataset.gain ? Number(e.dataset.gain) : null)")

        initial = page.eval_on_selector_all(
            "tbody tr", "els => els.slice(0, 5).map(r => r.textContent.slice(0, 24))")

        def monotone(seq, descending=True):
            vals = [x for x in seq if x is not None]
            return all(
                (vals[i] >= vals[i + 1]) if descending else (vals[i] <= vals[i + 1])
                for i in range(len(vals) - 1))

        click_header()
        desc = gains()
        check("режим 1: по приросту по убыванию",
              desc[0] == max(v for v in desc if v is not None) and monotone(desc, True),
              f"первые={desc[:6]}")

        click_header()
        asc = gains()
        check("режим 2: по приросту по возрастанию", monotone(asc, False), f"первые={asc[:6]}")
        check("в режиме «возрастание» строки без данных тоже в конце",
              all(v is not None for v in asc), f"первые={asc[:4]}")

        click_header()
        ratios = page.eval_on_selector_all(
            "tbody tr td.pr-gain",
            "els => els.slice(0, 10).map(e => e.dataset.ratio ? Number(e.dataset.ratio) : null)")
        check("режим 3: по росту в разах",
              ratios[0] is not None and monotone(ratios, True),
              f"первые={[round(r, 2) if r else r for r in ratios[:6]]}")

        click_header()
        jumps = page.eval_on_selector_all(
            "tbody tr td.pr-gain",
            "els => els.slice(0, 10).map(e => e.dataset.jump ? Number(e.dataset.jump) : null)")
        check("режим 4: по прыжку в топе",
              jumps[0] is not None and monotone(jumps, True), f"первые={jumps[:6]}")

        click_header()
        after = page.eval_on_selector_all(
            "tbody tr", "els => els.slice(0, 5).map(r => r.textContent.slice(0, 24))")
        check("режим 0: исходный порядок восстановлен", initial == after, str(after[:2]))

        # вторая колонка: прирост в процентах от текущего числа вишлистов
        pct_cells = page.eval_on_selector_all("tbody tr td.pr-pct", "els => els.length")
        check("колонка «% прироста» добавлена в строки", pct_cells > 500, f"ячеек={pct_cells}")
        pct_head = page.text_content("th[data-pr-pct]") or ""
        check("заголовок колонки «% прироста»", pct_head.startswith("Change %"), pct_head)
        pct_first = page.eval_on_selector("tbody tr td.pr-pct", "e => e.textContent")
        check("значение в ячейке — процент", pct_first.endswith("%"), f"значение={pct_first}")

        def click_pct():
            page.eval_on_selector("th[data-pr-pct]", "el => el.click()")
            page.wait_for_timeout(500)

        def pcts(limit=12):
            return page.eval_on_selector_all(
                "tbody tr td.pr-pct",
                f"els => els.slice(0, {limit}).map(e => e.dataset.pct ? Number(e.dataset.pct) : None)")

        click_pct()
        pct_desc = pcts()
        check("сортировка по проценту по убыванию",
              pct_desc[0] is not None and monotone(pct_desc, True), f"первые={pct_desc[:6]}")

        click_pct()
        pct_asc = pcts()
        check("сортировка по проценту по возрастанию", monotone(pct_asc, False),
              f"первые={pct_asc[:6]}")

        click_pct()
        pct_order = page.eval_on_selector_all(
            "tbody tr", "els => els.slice(0, 5).map(r => r.textContent.slice(0, 24))")
        check("после сортировки по проценту порядок восстановлен", initial == pct_order,
              str(pct_order[:2]))

        last_has_data = page.eval_on_selector(
            "tbody tr:last-child td.pr-gain", "e => Boolean(e.dataset.gain)")
        check("строки без данных уходят в конец", last_has_data is False)

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

