"""Разбор страницы фестиваля PlayRecon: вытащить таблицу демо из HTML.

Страница отдаётся без авторизации и присылает данные в RSC-потоке Next.js
(`self.__next_f.push`), поэтому парсим не DOM, а встроенный JSON: находим объекты
с полями строки таблицы и собираем их в JSONL.

Запуск:
    python scripts/scrape_playrecon_fest.py                 # oct-2026, top=1000
    python scripts/scrape_playrecon_fest.py --refresh       # перекачать HTML
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
HTML = CACHE / "playrecon_fest.html"
OUT = CACHE / "playrecon_fest_rows.jsonl"
URL = "https://app.playrecon.com/fests/nextfest/autumn-2026"

PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)', re.S)
APPID_RE = re.compile(r'\{"appid":\d+')
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0.0.0 Safari/537.36"}


def fetch(refresh: bool) -> str:
    if HTML.exists() and not refresh:
        return HTML.read_text(encoding="utf-8", errors="replace")
    resp = requests.get(URL, params={"top": 1000, "sort": "players", "dir": "desc"},
                        headers=UA, timeout=120)
    resp.raise_for_status()
    HTML.write_text(resp.text, encoding="utf-8")
    return resp.text


def rsc_text(html: str) -> str:
    """Склеить RSC-поток: каждый push — строка в кавычках с JSON-экранированием."""
    parts: list[str] = []
    for raw in PUSH_RE.findall(html):
        try:
            parts.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def object_at(text: str, start: int, max_span: int = 4000) -> dict | None:
    depth = 0
    in_str = False
    esc = False
    limit = min(len(text), start + max_span)
    for i in range(start, limit):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    if args.probe:
        text = rsc_text(fetch(args.refresh))
        OUTP = CACHE / "playrecon_fest_probe.txt"
        lines: list[str] = [f"RSC {len(text)} символов"]
        for token in ("appid", "wlEst", "wlBefore", "wl", "peak", "players", "wishlist", "demo"):
            lines.append(f"'{token}': {text.count(token)} вхождений")
        for m in list(re.finditer(r'appid', text))[:3]:
            lines.append("--- контекст: " + text[max(0, m.start() - 150): m.start() + 450].replace("\\n", " "))
        OUTP.write_text("\n".join(lines), encoding="utf-8")
        print(f"проба: {OUTP} ({OUTP.stat().st_size} байт)")
        return 0

    html = fetch(args.refresh)
    text = rsc_text(html)
    print(f"HTML {len(html) // 1024} КБ, RSC {len(text) // 1024} КБ")

    rows: dict[int, dict] = {}
    for m in APPID_RE.finditer(text):
        obj = object_at(text, m.start())
        if not isinstance(obj, dict) or not obj.get("name"):
            continue
        appid = int(obj["appid"])
        if appid not in rows or len(obj) > len(rows[appid]):
            rows[appid] = obj

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows.values()),
                   encoding="utf-8")
    print(f"строк с названием: {len(rows)} -> {OUT.name}")
    if rows:
        sample = next(iter(rows.values()))
        print("поля строки:", ", ".join(sample.keys()))
        print("пример:", json.dumps(sample, ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
