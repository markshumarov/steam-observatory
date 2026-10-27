"""Опрос MCP по выборке демо вне борда: есть ли у них вишлист-ранг и прирост.

Каждый вызов get_app_demand стоит ~1.9 CU, поэтому пишем компактно и с
докачкой: повторный запуск продолжает с того места, где остановились.

Запуск: python scripts/fetch_demand_sample.py
Вход:   data/cache/sample_outside_board.json
Выход:  data/cache/sample_outside_board_calls.jsonl (по строке на игру)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
ENDPOINT = "https://app.playrecon.com/api/mcp"
PROTOCOL = "2025-06-18"
OUT = CACHE / "sample_outside_board_calls.jsonl"
FROM = "2026-09-01"


def token() -> str:
    return (CACHE / "playrecon_token.txt").read_text(encoding="utf-8").strip()


def parse(resp: requests.Response) -> dict:
    if "text/event-stream" in resp.headers.get("content-type", ""):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                    return obj
        return {"error": {"message": "пустой SSE"}}
    try:
        return resp.json()
    except ValueError:
        return {"error": {"message": f"HTTP {resp.status_code}"}}


class Client:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers.update(
            {
                "Authorization": f"Bearer {token()}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )
        self.session_id: str | None = None
        self.next_id = 1
        body = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "steam-observatory", "version": "0.1"},
            },
        }
        self.next_id += 1
        r = self.s.post(ENDPOINT, json=body, timeout=90)
        if sid := r.headers.get("mcp-session-id"):
            self.session_id = sid
        self.s.post(
            ENDPOINT,
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            headers={"mcp-session-id": self.session_id} if self.session_id else {},
            timeout=90,
        )

    def call(self, name: str, arguments: dict) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self.next_id += 1
        r = self.s.post(
            ENDPOINT,
            json=body,
            headers={"mcp-session-id": self.session_id} if self.session_id else {},
            timeout=120,
        )
        if r.status_code >= 400:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
        return parse(r)


def main() -> int:
    sample = json.loads((CACHE / "sample_outside_board.json").read_text(encoding="utf-8"))
    done: set[int] = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["appid"])
    todo = [g["appid"] for g in sample["games"] if g["appid"] not in done]
    print(f"всего в выборке: {sample['n']}, уже снято: {len(done)}, осталось: {len(todo)}", flush=True)

    client = Client()
    spent = 0.0
    with OUT.open("a", encoding="utf-8") as fh:
        for i, appid in enumerate(todo, 1):
            out = client.call("get_app_demand", {"appid": appid, "from": FROM})
            result = out.get("result") or {}
            payload = result.get("structuredContent") or {}
            data = payload.get("data") or {}
            cu = ((result.get("_meta") or {}).get("cu") or {})
            spent += float(cu.get("charged") or 0)
            row = {
                "appid": appid,
                "name": data.get("name"),
                "coming_soon": data.get("coming_soon"),
                "release_day": data.get("release_day"),
                # подписчики: для игр вне вишлист-чарта это единственный сигнал интереса
                "followers": data.get("followers"),
                "wishlists": data.get("wishlists"),
                "wishlist_ranks": data.get("wishlist_ranks"),
                "warnings": [w.get("code") for w in (payload.get("warnings") or [])],
                "error": (out.get("error") or {}).get("message"),
                "cu": cu.get("charged"),
                "cu_left": (cu.get("month") or {}).get("cuLeft"),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} — потрачено {spent:.1f} CU, остаток {row['cu_left']}",
                      flush=True)
            time.sleep(0.3)
    print("готово", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
