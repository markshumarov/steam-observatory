"""Рендер страницы Steam headless-браузером (Edge/Chrome) и разбор DOM.

Проверяем, можно ли получить список участников фестиваля после исполнения JS,
и подчиняется ли он параметру `offset` (постраничный обход).

Запуск: python scripts/probe_headless.py [url] [offset]
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str:
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    raise SystemExit("браузер не найден")


def dump(url: str, budget: int = 25000) -> str:
    exe = find_browser()
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            exe,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={tmp}",
            f"--virtual-time-budget={budget}",
            "--dump-dom",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return res.stdout or ""


url = sys.argv[1] if len(sys.argv) > 1 else config.NEXTFEST_PAGE
if len(sys.argv) > 2:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}offset={sys.argv[2]}"

html = dump(url)
print(f"url: {url}\nDOM: {len(html)} байт")
links = sorted({int(x) for x in re.findall(r"/app/(\d+)/", html)})
print(f"уникальных appid в ссылках: {len(links)}")
print("первые:", links[:20])
print("store_item_keys:", html.count("store_item_keys"), "| appids:", html.count("appids"))
print("data-browser_:", len(re.findall(r"data-browser_", html)))

out = config.CACHE_DIR / "headless_dom.html"
out.write_text(html, encoding="utf-8")
print("DOM сохранён:", out)
