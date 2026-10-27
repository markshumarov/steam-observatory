"""Найти строки файла с испорченной кодировкой (двойное кодирование cp1251/utf-8).

Запуск: python scripts/_scan_encoding.py site/story.js
"""

from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

# признаки двойного кодирования: «Р»/«С» + строчная кириллица, «вЂ», «В·», U+FFFD
markers = ("В·", "вЂ", "вЂ“", "\ufffd")
hits = []
for i, line in enumerate(text.splitlines(), 1):
    if any(m in line for m in markers):
        hits.append((i, line))
    elif "Р" in line or "С" in line:
        # кириллица в коде может быть только в комментариях/строках — считаем это признаком
        if any(ch.islower() and "\u0400" <= ch <= "\u04ff" for ch in line):
            hits.append((i, line))

print(f"строк с признаками порчи: {len(hits)} из {len(text.splitlines())}")
for i, line in hits[:40]:
    print(f"{i:5}: {line.strip()[:110]}")
