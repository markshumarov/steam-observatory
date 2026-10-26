"""Подключение к MCP-серверу PlayRecon напрямую по HTTP (JSON-RPC).

Cline в этом окружении не умеет сам ходить в MCP, но транспорт у MCP — обычный
HTTP: initialize -> notifications/initialized -> tools/list -> tools/call.
Ответы могут приходить как JSON или как SSE (`data: {...}`), поэтому разбираем оба.

Токен читается из data/cache/playrecon_token.txt (папка в .gitignore).

Запуск:
    python scripts/playrecon_probe.py list
    python scripts/playrecon_probe.py call <tool> '{json}'
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / "data" / "cache" / "playrecon_token.txt"
ENDPOINT = "https://app.playrecon.com/api/mcp"
PROTOCOL = "2025-06-18"


def token() -> str:
    return TOKEN_FILE.read_text(encoding="utf-8").strip()


def parse(resp: requests.Response) -> dict:
    """Ответ MCP: либо JSON, либо SSE-поток с одной или несколькими data-строками."""
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        payloads = [
            line[5:].strip()
            for line in resp.text.splitlines()
            if line.startswith("data:")
        ]
        for raw in payloads:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                return obj
        return {"error": {"message": "пустой SSE", "raw": resp.text[:400]}}
    try:
        return resp.json()
    except ValueError:
        return {"error": {"message": f"не JSON (HTTP {resp.status_code})", "raw": resp.text[:400]}}


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

    def _post(self, method: str, params: dict | None = None, notify: bool = False):
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            body["id"] = self.next_id
            self.next_id += 1
        headers = {"mcp-session-id": self.session_id} if self.session_id else {}
        resp = self.s.post(ENDPOINT, json=body, headers=headers, timeout=90)
        if sid := resp.headers.get("mcp-session-id"):
            self.session_id = sid
        if resp.status_code >= 400:
            return {"error": {"message": f"HTTP {resp.status_code}", "raw": resp.text[:400]}}
        return {} if notify else parse(resp)

    def initialize(self) -> dict:
        out = self._post(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "steam-observatory", "version": "0.1"},
            },
        )
        self._post("notifications/initialized", {}, notify=True)
        return out

    def list_tools(self) -> dict:
        return self._post("tools/list", {})

    def call(self, name: str, arguments: dict) -> dict:
        return self._post("tools/call", {"name": name, "arguments": arguments})


def main() -> int:
    # консоль Windows не умеет UTF-8 по умолчанию, а в описаниях есть × и другие символы
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    c = Client()
    init = c.initialize()
    if "error" in init:
        print("ОШИБКА initialize:", json.dumps(init["error"], ensure_ascii=False)[:500])
        return 1
    info = init.get("result", {}).get("serverInfo", {})
    print("сервер:", json.dumps(info, ensure_ascii=False))
    print("протокол:", init.get("result", {}).get("protocolVersion"))
    print("инструкции:", (init.get("result", {}).get("instructions") or "")[:600])

    if mode == "list":
        tools = c.list_tools()
        items = tools.get("result", {}).get("tools", [])
        dump = ROOT / "data" / "cache" / "playrecon_tools.json"
        dump.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nинструментов: {len(items)}; полный список: {dump}")
        for t in items:
            schema = t.get("inputSchema", {}) or {}
            props = ", ".join((schema.get("properties") or {}).keys())
            req = ", ".join(schema.get("required") or [])
            print(f"\n* {t['name']}: {(t.get('description') or '').strip()[:400]}")
            print(f"    аргументы: {props}")
            if req:
                print(f"    обязательные: {req}")
        return 0

    if mode == "brief":
        tools = json.loads((ROOT / "data" / "cache" / "playrecon_tools.json").read_text(encoding="utf-8"))
        for t in tools:
            schema = t.get("inputSchema") or {}
            props = ", ".join((schema.get("properties") or {}).keys())
            req = ", ".join(schema.get("required") or [])
            desc = " ".join((t.get("description") or "").split())
            cost = ""
            if m := re.search(r"(Free \(0 CU\)|Cost:[^.]*\.)", desc):
                cost = m.group(1)
            print(f"{t['name']:38} {cost[:60]:60} [{props}] {'REQ:' + req if req else ''}")
        return 0

    if mode == "metrics":
        raw = json.loads((ROOT / "data" / "cache" / "playrecon_describe_metrics.json").read_text(encoding="utf-8"))
        payload = (raw.get("result") or {}).get("structuredContent") or {}
        metrics = ((payload.get("data") or {}).get("metrics")) or []
        print(f"метрик: {len(metrics)}")
        for m in metrics:
            print(
                f"{m.get('metric_key',''):34} {m.get('unit',''):16} "
                f"{(m.get('display_name') or '')[:44]:46} "
                f"from {m.get('available_from') or '-':12} "
                f"{'estimate' if m.get('estimated') else 'observed'}"
            )
        return 0

    if mode == "calljson":
        # аргументы из файла: удобно для вложенных filters и не ломается кавычками
        name = sys.argv[2]
        args = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        out = c.call(name, args)
        dump = ROOT / "data" / "cache" / f"playrecon_{name}_{abs(hash(json.dumps(args, sort_keys=True))) % 100000}.json"
        dump.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        meta = (out.get("result") or {}).get("_meta", {})
        print("CU:", json.dumps(meta, ensure_ascii=False)[:300])
        print(f"ответ: {dump} ({dump.stat().st_size} байт)")
        payload = (out.get("result") or {}).get("structuredContent")
        if payload is None:
            text = ((out.get("result") or {}).get("content") or [{}])[0].get("text", "")
            try:
                payload = json.loads(text)
            except (ValueError, TypeError):
                payload = text
        print(json.dumps(payload, ensure_ascii=False, indent=1)[:3000])
        return 0

    if mode == "call":
        name = sys.argv[2]
        args: dict = {}
        for raw in sys.argv[3:]:
            key, _, value = raw.partition("=")
            if not _:
                continue
            if value.lstrip("-").isdigit():
                args[key] = int(value)
            elif value.lower() in ("true", "false"):
                args[key] = value.lower() == "true"
            elif value[:1] in "[{":
                args[key] = json.loads(value)
            else:
                args[key] = value
        out = c.call(name, args)
        # кэш ответа: каждый вызов стоит CU, повторять его не нужно
        dump = ROOT / "data" / "cache" / f"playrecon_{name}.json"
        dump.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        meta = (out.get("result") or {}).get("_meta", {})
        print("CU:", json.dumps(meta, ensure_ascii=False)[:300])
        print(f"ответ: {dump} ({dump.stat().st_size} байт)")
        # structuredContent — то же самое, но разобранным JSON: печатаем его
        payload = (out.get("result") or {}).get("structuredContent")
        if payload is None:
            text = ((out.get("result") or {}).get("content") or [{}])[0].get("text", "")
            try:
                payload = json.loads(text)
            except (ValueError, TypeError):
                payload = text
        print(json.dumps(payload, ensure_ascii=False, indent=1)[:4500])
        return 0

    print("режимы: list | call <tool> <json>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
