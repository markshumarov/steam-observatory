"""Официальные публичные эндпоинты Steam.

Все запросы — к публичным поверхностям Steam, без ключей и без авторизации.
"""

from __future__ import annotations

import logging

import requests

from .. import config

log = logging.getLogger(__name__)

# Тег, которым Valve помечает игры фестиваля Next Fest (виден в запросе страницы).
NEXTFEST_TAGID = "1458863"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


def dynamic_sale_items(
    tagid: str = NEXTFEST_TAGID,
    *,
    cc: str = "us",
    max_results: int = 10000,
    s: requests.Session | None = None,
) -> dict:
    """Полный список игр фестиваля (то, что запрашивает сама страница Next Fest).

    Возвращает dict с ключами:
      rgCapsules          — [{"id": appid, "type": "game"}, ...] (полный состав)
      rgSolrFacetCounts   — {tagid: количество игр} по всему фестивалю
      nMatchCount         — общее число совпадений
      bMoreResultsRemaining — остались ли непоказанные результаты
    """
    s = s or session()
    s.get(config.NEXTFEST_PAGE, timeout=config.REQUEST_TIMEOUT_S)  # прогрев сессии
    resp = s.get(
        "https://store.steampowered.com/actions/ajaxgetdynamicsaleitems",
        params={
            "origin": "https://store.steampowered.com",
            "max_results": str(max_results),
            "cc": cc,
            "tagids_featured": tagid,
        },
        headers={"Referer": config.NEXTFEST_PAGE, "X-Requested-With": "XMLHttpRequest"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def appdetails(
    appids: list[int] | list[str],
    *,
    cc: str = "us",
    lang: str = "english",
    filters: str | None = "basic",
    s: requests.Session | None = None,
) -> dict:
    """Метаданные игр пачкой. Steam принимает список appid через запятую."""
    s = s or session()
    params = {"appids": ",".join(str(a) for a in appids), "cc": cc, "l": lang}
    if filters:
        params["filters"] = filters
    resp = s.get(
        f"{config.STEAM_STORE}/api/appdetails", params=params, timeout=config.REQUEST_TIMEOUT_S
    )
    resp.raise_for_status()
    return resp.json()


def current_players(appid: int | str, *, s: requests.Session | None = None) -> int | None:
    """Игроков прямо сейчас (без ключа). None, если Steam не отдал число."""
    s = s or session()
    resp = s.get(
        f"{config.STEAM_API}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
        params={"appid": appid},
        timeout=config.REQUEST_TIMEOUT_S,
    )
    if resp.status_code != 200:
        return None
    data = resp.json().get("response", {})
    if data.get("result") != 1:
        return None
    return int(data.get("player_count", 0))


def review_count(appid: int | str, *, s: requests.Session | None = None) -> dict | None:
    """Сводка отзывов: сколько всего, сколько положительных."""
    s = s or session()
    resp = s.get(
        f"{config.STEAM_STORE}/appreviews/{appid}",
        params={"json": 1, "num_per_page": 0, "language": "all", "purchase_type": "all"},
        timeout=config.REQUEST_TIMEOUT_S,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data.get("success"):
        return None
    summary = data.get("query_summary", {})
    return {
        "total": summary.get("total_reviews"),
        "positive": summary.get("total_positive"),
        "negative": summary.get("total_negative"),
        "score_desc": summary.get("review_score_desc"),
    }
