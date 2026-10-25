"""HTTP-клиент: вежливый rate limit, ретраи, дисковый кэш.

Все внешние запросы идут через `get()`. Кэш на диске обязателен: скрипты
перезапускаются часто, а Wayback Machine отвечает медленно.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": config.USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    }
)

_last_call = [0.0]


def _throttle() -> None:
    delta = time.time() - _last_call[0]
    if delta < config.REQUEST_DELAY_S:
        time.sleep(config.REQUEST_DELAY_S - delta)
    _last_call[0] = time.time()


def cache_path(url: str, suffix: str = ".bin") -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return config.CACHE_DIR / f"{key}{suffix}"


def get_bytes(
    url: str,
    *,
    params: dict | None = None,
    use_cache: bool = True,
    suffix: str = ".bin",
    timeout: int | None = None,
    headers: dict | None = None,
) -> bytes:
    """GET с кэшем на диске. Возвращает тело ответа (bytes)."""
    full = url if not params else f"{url}?{sorted(params.items())}"
    cp = cache_path(full, suffix)
    if use_cache and cp.exists() and cp.stat().st_size > 0:
        log.debug("cache hit: %s", cp.name)
        return cp.read_bytes()

    last_err = "unknown"
    for attempt in range(1, config.MAX_RETRIES + 1):
        _throttle()
        try:
            resp = _session.get(
                url,
                params=params,
                timeout=timeout or config.REQUEST_TIMEOUT_S,
                headers=headers,
            )
        except requests.RequestException as exc:  # сеть, таймаут, TLS
            last_err = repr(exc)
            time.sleep(min(2**attempt, 30))
            continue

        if resp.status_code == 200 and resp.content:
            cp.write_bytes(resp.content)
            return resp.content
        if resp.status_code in (429, 500, 502, 503, 504):
            last_err = f"HTTP {resp.status_code}"
            time.sleep(min(2**attempt, 30))
            continue
        raise RuntimeError(f"HTTP {resp.status_code} for {url}")

    raise RuntimeError(f"giving up after {config.MAX_RETRIES} tries: {last_err} ({url})")


def get_text(url: str, **kwargs) -> str:
    return get_bytes(url, **kwargs).decode("utf-8", "replace")


def get_json(url: str, **kwargs):
    import json

    return json.loads(get_text(url, **kwargs))
