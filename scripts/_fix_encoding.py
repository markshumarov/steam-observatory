"""Починка кодировки файла после правки через PowerShell.

Get-Content без -Encoding прочитал UTF-8 как cp1251, и Set-Content записал
испорченный текст. Обратное преобразование: текст -> cp1251 -> utf-8.

Запуск: python scripts/_fix_encoding.py site/story.js
"""

from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
fixed = text.encode("cp1251", errors="replace").decode("utf-8", errors="replace")
path.write_text(fixed, encoding="utf-8", newline="")
print(f"исправлено: {path} ({len(text)} -> {len(fixed)} символов)")
print("пример:", [line for line in fixed.splitlines() if "·" in line][:1])
