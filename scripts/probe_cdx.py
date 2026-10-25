"""Поиск в Wayback по префиксу URL: какие запросы (в т.ч. XHR) сохранены.

Запуск: python scripts/probe_cdx.py <url-префикс> <from YYYYMMDD> <to YYYYMMDD>
Пример: python scripts/probe_cdx.py store.steampowered.com/saleaction/ 20230619 20230730
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs.http import get_text  # noqa: E402

prefix = sys.argv[1] if len(sys.argv) > 1 else "store.steampowered.com/saleaction/"
frm = sys.argv[2] if len(sys.argv) > 2 else "20230601"
to = sys.argv[3] if len(sys.argv) > 3 else "20230801"

params = {
    "url": prefix,
    "matchType": "prefix",
    "output": "json",
    "from": frm,
    "to": to,
    "limit": "300",
    "collapse": "urlkey",
    "fl": "timestamp,original,mimetype,statuscode,length",
}
body = get_text("http://web.archive.org/cdx/search/cdx", params=params, suffix=".json")

import json  # noqa: E402

try:
    rows = json.loads(body)
except json.JSONDecodeError:
    print("не JSON:", body[:300])
    raise SystemExit(1)

print(f"префикс: {prefix}  окно: {frm}..{to}  строк: {max(0, len(rows) - 1)}")
if len(rows) < 2:
    raise SystemExit(0)

header, data = rows[0], rows[1:]
by_url: dict[str, list] = collections.defaultdict(list)
for row in data:
    rec = dict(zip(header, row))
    by_url[rec["original"]].append(rec)

print(f"уникальных URL: {len(by_url)}\n")
for url, recs in sorted(by_url.items(), key=lambda kv: -max(int(r["length"] or 0) for r in kv[1]))[:40]:
    biggest = max(recs, key=lambda r: int(r["length"] or 0))
    print(f"  {len(recs):>3}x  {int(biggest['length'] or 0):>9}  {biggest['mimetype']:16} {biggest['statuscode']}  {url[:150]}")
