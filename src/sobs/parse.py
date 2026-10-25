"""Разбор HTML-страницы Steam Next Fest в структурированный список игр.

Стратегии (по убыванию качества):
1. `json_objects` — находим JSON-объекты вида {"appid":123,...,"tags":[...]}.
   Даёт максимум полей: название, теги, дата релиза, цена, отзывы.
2. `appid_regex`   — только идентификаторы (если структура изменилась).
3. `app_links`     — ссылки /app/<id>/ (последний резерв).
"""

from __future__ import annotations

import html as html_mod
import json
import re

APPID_OBJ_RE = re.compile(r'\{\s*"appid"\s*:\s*\d+')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
APPID_RE = re.compile(r'"appid"\s*:\s*(\d+)')
APP_LINK_RE = re.compile(r"/app/(\d+)/")


def page_title(html: str) -> str:
    m = TITLE_RE.search(html)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _json_object_at(text: str, start: int, max_span: int = 20000) -> str | None:
    """Вырезать JSON-объект, начинающийся на `start`, с учётом строк и экранирования."""
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
                return text[start : i + 1]
    return None


def _unescape_variants(html: str):
    """Страницы Steam отдают вложенный JSON с разным экранированием.

    2021: обычный JSON. 2023+: JSON внутри HTML-атрибута, где кавычки
    закодированы как `&quot;` и/или `\\"` (иногда двойной бэкслеш).
    Поэтому пробуем несколько нормализаций и берём ту, что даёт больше игр.
    """
    once = html_mod.unescape(html)
    twice = html_mod.unescape(once)

    def strip_bs(text: str) -> str:
        # один или несколько бэкслешей перед кавычкой -> просто кавычка
        return re.sub(r'\\+"', '"', text)

    return [
        ("raw", html),
        ("unescape", once),
        ("unescape+bs", strip_bs(once)),
        ("unescape2", twice),
        ("unescape2+bs", strip_bs(twice)),
    ]


def _games_via_backscan(text: str, window: int = 4000, max_candidates: int = 6) -> list[dict]:
    """Найти все JSON-объекты, содержащие "appid", независимо от порядка ключей.

    Для каждого вхождения `"appid":N` идём назад к ближайшей `{` и проверяем,
    получается ли из неё корректный объект с этим appid.
    """
    found: dict[int, dict] = {}
    for m in APPID_RE.finditer(text):
        appid = int(m.group(1))
        if appid in found:
            continue
        cursor = m.start()
        for _ in range(max_candidates):
            b = text.rfind("{", max(0, cursor - window), cursor)
            if b < 0:
                break
            raw = _json_object_at(text, b, max_span=window * 2)
            if raw and b + len(raw) > m.start():
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict) and obj.get("appid") == appid:
                    found[appid] = obj
                    break
            cursor = b
    return list(found.values())


def _objects_forward(text: str) -> list[dict]:
    """Объекты, начинающиеся с {"appid": ...} — карточки игр."""
    out: list[dict] = []
    for m in APPID_OBJ_RE.finditer(text):
        raw = _json_object_at(text, m.start())
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("appid"), int) and obj["appid"] > 0:
            out.append(obj)
    return out


def _games_from_json_objects(text: str) -> list[dict]:
    """Слить кандидатов обоих проходов, оставив самый богатый объект на appid."""
    cands: dict[int, dict] = {}
    for obj in _objects_forward(text) + _games_via_backscan(text):
        appid = obj.get("appid")
        if not isinstance(appid, int) or appid <= 0:
            continue
        prev = cands.get(appid)
        if prev is None or len(obj) > len(prev):
            cands[appid] = obj
    return list(cands.values())


def extract_games(html: str) -> tuple[list[dict], str]:
    """Вернуть (список игр, какая стратегия сработала)."""
    best: list[dict] = []
    best_strategy = "none"

    for name, text in _unescape_variants(html):
        games = _games_from_json_objects(text)
        if len(games) > len(best):
            best, best_strategy = games, f"json_objects[{name}]"
    if best:
        return best, best_strategy

    for name, text in _unescape_variants(html):
        ids = {int(x) for x in APPID_RE.findall(text)}
        ids |= {int(x) for x in APP_LINK_RE.findall(text)}
        for chunk in re.findall(r'data-ds-appid="([\d,]+)"', text):
            ids |= {int(x) for x in chunk.split(",") if x.isdigit()}
        if ids:
            return [{"appid": i} for i in sorted(ids)], f"id_only[{name}]"

    return [], "none"


def normalize_game(g: dict) -> dict:
    """Схема записи участника фестиваля (стабильная, версионируется)."""
    tags = [t for t in (g.get("tags") or []) if isinstance(t, dict)]
    rev = g.get("reviews_filtered") or {}
    return {
        "appid": g.get("appid"),
        "title": g.get("title") or g.get("name") or "",
        "type": g.get("type") or "game",
        "release": g.get("release") or "",
        "coming_soon": bool(g.get("coming_soon", False)),
        "early_access": bool(g.get("early_access", False)),
        "is_free": bool(g.get("is_free", False)),
        "price_cents": g.get("price_in_cents"),
        "platforms": {
            "win": bool(g.get("available_windows", False)),
            "mac": bool(g.get("available_mac", False)),
            "linux": bool(g.get("available_linux", False)),
        },
        "reviews": {
            "n": rev.get("num_reviews"),
            "positive": rev.get("num_positive"),
            "score": rev.get("score"),
        },
        "content_descriptors": g.get("content_descriptors") or [],
        "tags": [t.get("name") for t in tags if t.get("name")],
        "tag_ids": [t.get("tagid") for t in tags if t.get("tagid")],
        "n_screenshots": len(g.get("screenshot_list") or []),
        "has_microtrailer": bool(g.get("microtrailer") or g.get("microtrailer_mp4")),
        "creator_clan_ids": g.get("creator_clan_ids") or [],
        "localized_langs": g.get("localized_langs") or [],
    }
