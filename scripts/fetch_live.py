"""Загрузить живую страницу Steam Next Fest (и сохранить в кэш).

Запуск: python scripts/fetch_live.py [url]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs import config  # noqa: E402
from sobs.http import get_text  # noqa: E402

url = sys.argv[1] if len(sys.argv) > 1 else config.NEXTFEST_PAGE
text = get_text(url, use_cache=False)
print(f"{url}\n  {len(text)} байт")
for kw in ("sale_sections", "tagged_items", "sale_vanity_id", "clanAccountID"):
    print(f"  {kw}: {text.count(kw)}")
