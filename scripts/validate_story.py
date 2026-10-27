"""Проверка страницы-разбора: графики, выводы, переключение языка, ошибки консоли.

Запуск: python scripts/validate_story.py            # локально
        python scripts/validate_story.py <URL>      # развёрнутая версия
"""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from sobs import config  # noqa: E402

SITE = config.ROOT / "site"
PORT = 8796
TARGET = sys.argv[1] if len(sys.argv) > 1 else None

try:  # консоль Windows не умеет UTF-8 по умолчанию, а в текстах есть × и —
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # без шума в консоли
        pass


if TARGET is None:
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", PORT), functools.partial(Quiet, directory=str(SITE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    URL = f"http://127.0.0.1:{PORT}/story.html"
else:
    URL = TARGET if TARGET.endswith(".html") else TARGET.rstrip("/") + "/story.html"

errors: list[str] = []
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'OK  ' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def static_supply_check() -> None:
    """Составы на странице не должны расходиться с site/data/fests.json."""
    story_file = SITE / "data" / "story.json"
    fests_file = SITE / "data" / "fests.json"
    if not (story_file.exists() and fests_file.exists()):
        check("составы совпадают с fests.json", False, "нет файлов данных")
        return
    supply = {
        r["slug"]: r["games"]
        for r in (json.loads(story_file.read_text(encoding="utf-8")).get("supply") or [])
    }
    fresh = {
        r["slug"]: r["n_final"]
        for r in json.loads(fests_file.read_text(encoding="utf-8"))
        if r.get("n_final")
    }
    diff = {s: (supply.get(s), fresh[s]) for s in fresh if supply.get(s) != fresh[s]}
    check(
        "составы совпадают с fests.json",
        not diff,
        "; ".join(f"{s}: {a} вместо {b}" for s, (a, b) in diff.items())
        if diff
        else f"изданий={len(fresh)}",
    )


static_supply_check()


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_selector("#chart-supply svg", timeout=30000)
    page.wait_for_timeout(1200)

    svg = page.eval_on_selector_all(".chart svg", "els => els.length")
    check("графики нарисованы", svg >= 6, f"svg={svg}")

    kickers = page.eval_on_selector_all(".kicker", "els => els.map(e => e.textContent.trim())")
    check("крупные числа заполнены", all(k and k not in ("—",) for k in kickers), str(kickers))
    check("первый блок — тиры вишлистов", kickers and kickers[0].endswith("%"), f"первое={kickers[:1]}")

    tier_bars = page.eval_on_selector_all("#chart-tiers svg rect", "els => els.length")
    check("в графике тиров четыре тира плюс «не смогли померить»", tier_bars == 5,
          f"полос={tier_bars}")

    # число полос в графике составов = число изданий в fests.json: пропажа
    # издания (как февраль 2025) раньше проходила незамеченной
    supply_bars = page.eval_on_selector_all("#chart-supply svg rect", "els => els.length")
    editions_in_fests = len({
        r["slug"]
        for r in json.loads((SITE / "data" / "fests.json").read_text(encoding="utf-8"))
        if r.get("n_final")
    })
    check("в графике составов полоса на каждое издание", supply_bars == editions_in_fests,
          f"полос={supply_bars}, изданий={editions_in_fests}")

    gains_bars = page.eval_on_selector_all("#chart-gains svg rect", "els => els.length")
    check("в графике долей шесть бакетов плюс «не смогли померить»", gains_bars >= 7,
          f"полос={gains_bars}")
    wl_bars = page.eval_on_selector_all("#chart-wl svg rect", "els => els.length")
    check("в графике до/после две полосы на бакет", wl_bars >= 10, f"полос={wl_bars}")

    tiers_hint = page.text_content("#hint-tiers") or ""
    check("в подписи тиров прямо сказано, сколько не смогли померить",
          "could not measure" in tiers_hint and "461" in tiers_hint, tiers_hint[:70])
    kicker_tiers = (page.text_content("#k-tiers") or "").strip()
    check("доля бриллиантов считается от всего состава", kicker_tiers.startswith("1.2"),
          f"кикер={kicker_tiers}")

    tiers_text = page.text_content("#take-tiers") or ""
    check("тиры описаны в выводах", "Diamond" in tiers_text and "Silver" in tiers_text,
          tiers_text[:70])

    takes = page.eval_on_selector_all(".takeaways li", "els => els.length")
    check("выводы под блоками есть", takes >= 12, f"пунктов={takes}")

    items = page.eval_on_selector_all("#checklist li", "els => els.length")
    check("список «что делать» из 5 пунктов", items == 5, f"пунктов={items}")

    sources = page.eval_on_selector_all("#sources tbody tr", "els => els.length")
    check("источники с атрибуцией", sources >= 4, f"строк={sources}")

    h1_en = page.text_content("h1") or ""
    page.click('.lang button[data-lang="ru"]')
    page.wait_for_timeout(700)
    h1_ru = page.text_content("h1") or ""
    check("переключение языка работает", h1_en != h1_ru and page.evaluate("document.documentElement.lang") == "ru",
          h1_ru[:40])

    shot = config.OUT_DIR / "story_screenshot_ru.png"
    page.screenshot(path=str(shot), full_page=True)
    print("скриншот:", shot.name, shot.stat().st_size, "байт")

    page.click('.lang button[data-lang="en"]')
    page.wait_for_timeout(500)
    shot_en = config.OUT_DIR / "story_screenshot_en.png"
    page.screenshot(path=str(shot_en), full_page=True)
    print("скриншот:", shot_en.name, shot_en.stat().st_size, "байт")
    browser.close()

print("ошибок в консоли:", len(errors))
for e in errors[:8]:
    print("  ", e)
print("провалено проверок:", len(failures))
sys.exit(1 if failures or errors else 0)
