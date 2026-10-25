"""Что реально извлекается из сырых HTML-снапшотов 2021-2023.

Считаем по каждому файлу: объекты с appid, из них с названием, с тегами,
с капсулой; печатаем пример «отбракованного» объекта, чтобы понять,
чем отличается структура страницы в разных изданиях.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sobs.parse import _json_object_at, _unescape_variants  # noqa: E402

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "nextfest"
APPID_OBJ_RE = re.compile(r'\{\s*"appid"\s*:\s*\d+')


def name_of(obj: dict) -> str:
    return obj.get("title") or obj.get("name") or ""


def has_tags(obj: dict) -> bool:
    tags = obj.get("tags")
    return bool(isinstance(tags, list) and tags)


def census(path: Path) -> None:
    html = path.read_text(encoding="utf-8", errors="replace")
    raw_appid = html.count('"appid"')
    best: tuple[int, list[dict], str] = (0, [], "")
    for name, text in _unescape_variants(html):
        found: dict[int, dict] = {}
        for m in APPID_OBJ_RE.finditer(text):
            chunk = _json_object_at(text, m.start())
            if not chunk:
                continue
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            appid = obj.get("appid")
            if isinstance(appid, int) and appid > 0:
                if appid not in found or len(obj) > len(found[appid]):
                    found[appid] = obj
        if len(found) > len(best[1]):
            best = (len(found), list(found.values()), name)
        if len(found) > 400:
            break

    n, objs, variant = best
    with_name = [o for o in objs if name_of(o)]
    with_tags = [o for o in objs if has_tags(o)]
    with_capsule = [o for o in objs if o.get("capsule") or o.get("main_capsule") or o.get("tiny_capsule")]
    print(f"\n{path.name}  ({len(html) // 1024} КБ, «appid» в тексте: {raw_appid})")
    print(f"   вариант {variant!r}: объектов {n}, с названием {len(with_name)}, "
          f"с тегами {len(with_tags)}, с капсулой {len(with_capsule)}")
    if objs:
        sample_rejected = next((o for o in objs if not has_tags(o)), None)
        if sample_rejected:
            keys = sorted(sample_rejected)[:18]
            print(f"   без тегов, ключи: {keys}")
            print(f"   пример: {json.dumps(sample_rejected, ensure_ascii=False)[:220]}")
        sample_ok = with_tags[0] if with_tags else None
        if sample_ok:
            print(f"   с тегами: {json.dumps(sample_ok, ensure_ascii=False)[:200]}")


def main() -> int:
    only = sys.argv[1:] or [
        "oct2021_20211004054323.html",
        "feb2022_20220224132432.html",
        "jun2022_20220616212507.html",
        "oct2022_20221005204434.html",
        "feb2023_20230207170547.html",
        "jun2023_20230623014616.html",
        "oct2023_20231012181156.html",
    ]
    for name in only:
        path = RAW / name
        if path.exists():
            census(path)
        else:
            print(f"\n{name}: файла нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
