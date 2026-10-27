"""Проверка сайта: локальный сервер (или развёрнутый URL) + headless-браузер.

Проверяем то, что легко сломать незаметно:
  * графики нарисовались и их фон не белый (единая тёмная тема);
  * язык по умолчанию английский и переключается на русский;
  * в выборе тегов все теги, а поиск действительно фильтрует;
  * в разделе демо полный список: поиск и таблица по всем играм;
  * в консоли нет ошибок.

Запуск:
    python scripts/validate_site.py            # локальная папка site/
    python scripts/validate_site.py <URL>      # развёрнутый сайт
"""

from __future__ import annotations

import functools
import http.server
import re
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
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # без шума в консоли
            pass

    handler = functools.partial(Quiet, directory=str(SITE))
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
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'OK  ' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    # --- 0. ленивая загрузка ------------------------------------------------
    # Пока тяжёлый ccu.json в пути, страница не должна выглядеть пустой:
    # издания и теги рисуются из маленьких файлов, в блоке демо — скелетоны.
    # Задержку делаем внутри страницы: page.route со sleep блокирует сам Playwright.
    page.add_init_script(
        """
        const orig = window.fetch;
        window.fetch = (input, init) => {
          const url = typeof input === "string" ? input : input.url;
          if (url.includes("ccu.json")) {
            return new Promise((res) => setTimeout(() => res(orig(input, init)), 3000));
          }
          return orig(input, init);
        };
        """
    )
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1200)
    early_rows = page.eval_on_selector_all("#table-editions tbody tr", "els => els.length")
    early_chips = page.eval_on_selector_all(".chip", "els => els.length")
    early_skel = page.eval_on_selector_all("#ccu .skel", "els => els.length")
    check("издания и теги видны до загрузки демо", early_rows >= 8 and early_chips > 300,
          f"строк={early_rows}, чипов={early_chips}")
    check("во время загрузки демо видны скелетоны", early_skel > 0, f"скелетонов={early_skel}")
    page.wait_for_selector("#table-ccu tbody tr", timeout=30000)
    page.wait_for_timeout(400)
    check("после загрузки скелетоны убраны",
          page.eval_on_selector_all(".skel", "els => els.length") == 0)
    page.reload(wait_until="load", timeout=60000)
    page.wait_for_selector("#chart-editions svg", timeout=30000)
    # init-скрипт с задержкой действует и после перезагрузки — ждём блок демо
    page.wait_for_selector("#table-ccu tbody tr", timeout=30000)
    page.wait_for_timeout(600)

    # --- 1. язык ---------------------------------------------------------
    check("язык по умолчанию английский", page.evaluate("document.documentElement.lang") == "en")
    h2_tags = page.text_content("#tags h2") or ""
    check("заголовок тегов на английском", "Tag saturation" in h2_tags, h2_tags)

    # --- 2. графики и тема ----------------------------------------------
    svg = page.eval_on_selector_all("svg", "els => els.length")
    check("графиков не меньше 4", svg >= 4, f"svg={svg}")

    styles = page.evaluate(
        """() => {
        const out = {};
        out.body = getComputedStyle(document.body).backgroundColor;
        const c = document.querySelector('#chart-editions svg');
        out.chart = c ? getComputedStyle(c).backgroundColor : 'none';
        const s = document.querySelector('#chart-editions');
        out.box = getComputedStyle(s).backgroundColor;
        return out;
    }"""
    )
    check("фон графиков не белый", styles["chart"] in ("transparent", "rgba(0, 0, 0, 0)"), str(styles))
    check("фон контейнера графиков не белый", styles["box"] in ("transparent", "rgba(0, 0, 0, 0)"), str(styles))
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("нет горизонтальной прокрутки страницы", overflow <= 2, f"перелив={overflow}px")

    # --- подсказки: тёмный пузырь и светлый текст -------------------------
    page.hover("#chart-editions svg rect")
    page.wait_for_timeout(500)
    tip = page.evaluate(
        """() => {
            const g = Array.from(document.querySelectorAll('[aria-label="tip"]'))
                .find(el => el.querySelector('path'));
            if (!g) return null;
            const path = g.querySelector('path');
            const text = g.querySelector('text');
            const toRgb = (v) => v;
            return {
                bubble: toRgb(getComputedStyle(path).fill),
                stroke: toRgb(getComputedStyle(path).stroke),
                text: text ? toRgb(getComputedStyle(text).fill) : null,
                lines: text ? text.textContent.trim().slice(0, 40) : null,
            };
        }"""
    )
    def rgb_sum(value):
        nums = [int(x) for x in re.findall(r"\d+", value or "")]
        return sum(nums[:3]) if len(nums) >= 3 else None

    check("подсказка: пузырь тёмный",
          bool(tip) and (rgb_sum(tip["bubble"]) or 765) < 380, str(tip))
    check("подсказка: текст светлый",
          bool(tip) and (rgb_sum(tip["text"]) or 0) > 450, str(tip))

    # --- 3. данные -------------------------------------------------------
    rows_ed = page.eval_on_selector_all("#table-editions tbody tr", "els => els.length")
    check("таблица изданий заполнена", rows_ed >= 8, f"строк={rows_ed}")

    chips_all = page.eval_on_selector_all(".chip", "els => els.length")
    check("в выборе тегов все теги (не топ-14)", chips_all > 300, f"чипов={chips_all}")
    unnamed = page.eval_on_selector_all(
        ".chip", "els => els.filter(e => /^tag \\d+/.test(e.textContent.trim())).length"
    )
    check("в выборе нет тегов без названия", unnamed == 0, f"безымянных={unnamed}")

    page.fill("#tag-search", "rogue")
    page.wait_for_timeout(250)
    chips_q = page.eval_on_selector_all(".chip", "els => els.map(e => e.textContent.toLowerCase())")
    check(
        "поиск по тегам фильтрует",
        0 < len(chips_q) < chips_all and all("rogue" in c for c in chips_q),
        f"найдено={len(chips_q)}",
    )
    page.fill("#tag-search", "")
    page.wait_for_timeout(200)

    ccu_rows = page.eval_on_selector_all("#table-ccu tbody tr", "els => els.length")
    check("таблица демо содержит много игр", ccu_rows >= 200, f"строк={ccu_rows}")
    kpis = page.eval_on_selector_all(".kpi .v", "els => els.map(e => e.textContent)")
    check("KPI по демо заполнены", len(kpis) == 4 and all(k not in ("", "0") for k in kpis), str(kpis))

    page.fill("#ccu-search", "stronghold")
    page.wait_for_timeout(300)
    ccu_q = page.eval_on_selector_all("#table-ccu tbody tr", "els => els.map(e => e.textContent)")
    check(
        "поиск по демо находит игру вне топа",
        len(ccu_q) >= 1 and all("stronghold" in r.lower() for r in ccu_q),
        f"найдено={len(ccu_q)}",
    )
    page.fill("#ccu-search", "")
    page.wait_for_timeout(200)

    shot_en = config.OUT_DIR / "site_screenshot_en.png"
    page.screenshot(path=str(shot_en), full_page=True)

    # --- 4. переключение языка ------------------------------------------
    page.click('.lang button[data-lang="ru"]')
    page.wait_for_timeout(800)
    check("переключение на русский", page.evaluate("document.documentElement.lang") == "ru")
    h2_ru = page.text_content("#tags h2") or ""
    check("заголовок тегов по-русски", "Насыщенность" in h2_ru, h2_ru)
    # в контейнере тегов Plot рисует сам график и свотчи легенды — их несколько
    check(
        "графики перерисованы после смены языка",
        page.eval_on_selector_all("#chart-tags svg", "els => els.length") >= 2
        and page.eval_on_selector_all("#chart-tags svg path", "els => els.length") > 3,
    )
    # подписи изданий не должны дублировать год («Октябрь 2021 2021»)
    axis = page.eval_on_selector_all("#chart-editions svg text", "els => els.map(e => e.textContent)")
    check("в подписях изданий нет дубля года", not any(re.search(r"20\\d\\d", a) for a in axis),
          str(axis[:6]))

    shot_ru = config.OUT_DIR / "site_screenshot_ru.png"
    page.screenshot(path=str(shot_ru), full_page=True)
    print("скриншоты:", shot_en.name, shot_en.stat().st_size, "|", shot_ru.name, shot_ru.stat().st_size)
    browser.close()

print("ошибок в консоли:", len(errors))
for e in errors[:10]:
    print("  ", e)
print("провалено проверок:", len(failures))
sys.exit(1 if failures or errors else 0)
