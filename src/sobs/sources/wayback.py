"""Wayback Machine: поиск снапшотов страницы (CDX API) и загрузка копий.

Зачем: страница Steam Next Fest исторически отдавалась сервером целиком,
вместе с JSON-описанием участников (appid, название, теги). Архивные копии
этой страницы — единственный бесплатный способ восстановить состав прошлых
фестивалей вместе с тегами.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .. import config
from ..http import get_text

log = logging.getLogger(__name__)

CDX_ENDPOINT = f"{config.WAYBACK}/cdx/search/cdx"


@dataclass
class Snapshot:
    timestamp: str  # YYYYMMDDhhmmss
    original: str
    statuscode: str
    mimetype: str
    length: int

    @property
    def iso(self) -> str:
        t = self.timestamp
        return f"{t[0:4]}-{t[4:6]}-{t[6:8]}T{t[8:10]}:{t[10:12]}:{t[12:14]}Z"

    @property
    def raw_url(self) -> str:
        """`id_` отдаёт оригинальный ответ без обвязки Wayback."""
        return f"{config.WAYBACK}/web/{self.timestamp}id_/{self.original}"


def cdx(
    url: str,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    limit: int = 500,
    collapse: str | None = None,
    statuscode: str = "200",
    match_type: str | None = None,
) -> list[Snapshot]:
    """Список снапшотов URL за период (сортировать нужно самим)."""
    params = {
        "url": url,
        "output": "json",
        "limit": limit,
        "filter": f"statuscode:{statuscode}",
    }
    if match_type:
        params["matchType"] = match_type
    if from_ts:
        params["from"] = from_ts
    if to_ts:
        params["to"] = to_ts
    if collapse:
        params["collapse"] = collapse

    body = get_text(CDX_ENDPOINT, params=params, suffix=".json")
    try:
        rows = json.loads(body)
    except json.JSONDecodeError:
        log.warning("CDX вернул не-JSON для %s: %r", url, body[:200])
        return []
    if not rows or len(rows) < 2:
        return []

    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    out: list[Snapshot] = []
    for row in rows[1:]:
        try:
            out.append(
                Snapshot(
                    timestamp=row[idx["timestamp"]],
                    original=row[idx["original"]],
                    statuscode=row[idx["statuscode"]],
                    mimetype=row[idx["mimetype"]],
                    length=int(row[idx["length"]] or 0),
                )
            )
        except (KeyError, ValueError, IndexError):
            continue
    return out


def fetch_snapshot(snap: Snapshot) -> str:
    """Скачать содержимое снапшота (кэшируется на диске)."""
    return get_text(snap.raw_url, suffix=".html")
