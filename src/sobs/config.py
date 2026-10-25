"""Глобальная конфигурация проекта / Global configuration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
OUT_DIR = DATA_DIR / "processed"

for _d in (RAW_DIR, CACHE_DIR, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Представляемся честно: это исследовательский сбор данных.
USER_AGENT = (
    "steam-observatory/0.1 (research project; "
    "+https://github.com/markshumarov/steam-observatory) python-requests"
)

# Вежливые лимиты: не чаще ~1 запроса в секунду к внешним источникам.
REQUEST_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 90
MAX_RETRIES = 4

# Источники
WAYBACK = "http://web.archive.org"
NEXTFEST_PAGE = "https://store.steampowered.com/sale/nextfest"
STEAM_STORE = "https://store.steampowered.com"
STEAM_API = "https://api.steampowered.com"
