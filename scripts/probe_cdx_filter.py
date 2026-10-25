"""Поиск в Wayback по префиксу с regex-фильтром на оригинальный URL.

Запуск: python scripts/probe_cdx_filter.py <url-префикс> <from> <to> <regex>
Пример: python scripts/probe_cdx_filter.py steamdb.info/ 20220101 20240101 nextfest
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs.http import get_text  # noqa: E402

prefix = sys.argv[1]
frm = sys.argv[2]
to = sys.argv[3]
pattern = sys.argv[4]

params = {
    "url": prefix,
    "matchType": "prefix",
    "output": "json",
    "from": frm,
    "to": to,
    "limit": "500",
    "collapse": "urlkey",
    "filter": f"original:.*{pattern}.*",
    "fl": "timestamp,original,mimetype,statuscode,length",
}
body = get_text("http://web.archive.org/cdx/search/cdx", params=params, suffix=".json")

try:
    rows = json.loads(body)
except json.JSONDecodeError:
    print("не JSON:", body[:200])
    raise SystemExit(1)

print(f"префикс {prefix}, фильтр {pattern!r}, окно {frm}..{to}: строк {max(0, len(rows) - 1)}")
for row in rows[1:41]:
    print("  ", "  ".join(str(x) for x in row))
