"""Сводка по выборке демо вне борда: у скольких вообще есть вишлист-след.

Вход:  data/cache/sample_outside_board.json, sample_outside_board_calls.jsonl,
       sample_followers.json (если есть)
Выход: data/cache/outside_sample_report.json + печать в консоль

Запуск: python scripts/aggregate_outside_sample.py
"""

from __future__ import annotations

import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:  # консоль Windows не умеет UTF-8 по умолчанию, а в выводе есть → и ≈
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from sobs import config  # noqa: E402

CACHE = config.CACHE_DIR
FEST_START = "2026-10-19"
FEST_END = "2026-10-26"


def load_curve():
    """Кривая «место → вишлисты» из скрипта по борду (тот же метод, что и раньше)."""
    spec = importlib.util.spec_from_file_location(
        "prwg", ROOT / "scripts" / "playrecon_wishlist_gain.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = mod.load_rows()
    at, _pts = mod.curve(rows)
    return at


def rank_at(series: list[dict], day: str, mode: str = "last") -> int | None:
    """Место на последний день до day (mode=last) или первый после (mode=first)."""
    if mode == "last":
        cand = [p["rank"] for p in series if p.get("day", "") <= day]
    else:
        cand = [p["rank"] for p in series if p.get("day", "") >= day]
    return cand[-1] if (mode == "last" and cand) else (cand[0] if cand else None)


def main() -> int:
    sample = json.loads((CACHE / "sample_outside_board.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (CACHE / "sample_outside_board_calls.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    followers_file = CACHE / "sample_followers.json"
    _ = followers_file  # поле follower_count со страницы Steam оказалось негодным

    with_rank = [r for r in rows if r.get("wishlist_ranks")]
    at = load_curve()

    measured = []
    for r in with_rank:
        series = sorted(r["wishlist_ranks"], key=lambda p: p.get("day", ""))
        before = rank_at(series, FEST_START, "last")
        after = rank_at(series, FEST_END, "first") or rank_at(series, "9999-12-31", "last")
        est_before = at(before) if before else None
        est_after = at(after) if after else None
        measured.append(
            {
                "appid": r["appid"],
                "name": r.get("name"),
                "rank_before": before,
                "rank_after": after,
                "jump": (before - after) if (before and after) else None,
                "est_before": int(est_before) if est_before else None,
                "est_after": int(est_after) if est_after else None,
                "gain": int(est_after - est_before) if (est_before and est_after) else None,
            }
        )

    # пик игроков в демо — из нашего собственного опроса (0 CU, все 7 073 демо).
    # Это прямой ответ на «насколько это мелкие проекты».
    peaks: dict[int, int] = {}
    ccu_csv = config.ROOT / "site" / "data" / "ccu.csv"
    if ccu_csv.exists():
        for i, line in enumerate(ccu_csv.read_text(encoding="utf-8").splitlines()):
            if i == 0:
                continue
            parts = line.split(",")
            if len(parts) >= 5 and parts[3].isdigit() and parts[4].lstrip("-").isdigit():
                peaks[int(parts[3])] = int(parts[4])
    sample_peaks = [peaks[g["appid"]] for g in sample["games"] if g["appid"] in peaks]
    board_ids = set()
    html_file = CACHE / "playrecon_fest.html"
    if html_file.exists():
        import re

        board_ids = {
            int(m) for m in re.findall(r"appid\\?\":\s*(\d+)", html_file.read_text(
                encoding="utf-8", errors="replace"))
        }
    board_peaks = [p for a, p in peaks.items() if a in board_ids]

    def peak_stats(values: list[int]) -> dict:
        if not values:
            return {}
        s = sorted(values)
        return {
            "n": len(s),
            "median": s[len(s) // 2],
            "p90": s[int(0.9 * (len(s) - 1))],
            "max": s[-1],
            "share_le1": round(sum(1 for v in s if v <= 1) / len(s), 4),
            "share_ge10": round(sum(1 for v in s if v >= 10) / len(s), 4),
            "share_ge100": round(sum(1 for v in s if v >= 100) / len(s), 4),
        }

    n = len(rows)
    outside = sample["outside"]
    share = len(with_rank) / n if n else 0
    report = {
        "sampled": n,
        "outside_board": outside,
        "lineup": sample["lineup"],
        "with_wishlist_rank": len(with_rank),
        "share_with_rank": round(share, 4),
        "projected_with_rank": round(outside * share),
        "no_wishlist_trace": n - len(with_rank),
        "measured": measured,
        "peaks_sample": peak_stats(sample_peaks),
        "peaks_board": peak_stats(board_peaks),
        "peaks_lineup": peak_stats(list(peaks.values())),
        "notes": [
            "борд PlayRecon покрывает топ-1000 по игрокам (1011 строк, из них 461 с приростом)",
            "модель вишлистов откалибрована на ранги 45–5192, глубже — оценки нет",
            "выборка вне борда: случайная, seed 20261027",
        ],
    }
    out = CACHE / "outside_sample_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"выборка вне борда: {n} демо из {outside} (состав {sample['lineup']})")
    print(f"с вишлист-рангом: {len(with_rank)} ({share * 100:.1f}%) → "
          f"в пересчёте на всех {outside}: ~{report['projected_with_rank']} демо")
    print(f"без вишлист-следа: {report['no_wishlist_trace']} демо")
    for key, label in (("peaks_sample", "выборка вне борда"),
                       ("peaks_board", "борд (топ-1000)"),
                       ("peaks_lineup", "всё демо фестиваля")):
        p = report.get(key) or {}
        if p:
            print(f"пик игроков, {label}: n={p['n']}, медиана {p['median']}, p90 {p['p90']}, "
                  f"макс {p['max']}; ≤1 игрока {p['share_le1'] * 100:.0f}%, "
                  f"≥10 {p['share_ge10'] * 100:.0f}%, ≥100 {p['share_ge100'] * 100:.0f}%")
    print("измеренные (с рангом):")
    for m in measured:
        print(f"  {m['name']}: #{m['rank_before']}→#{m['rank_after']} "
              f"(прыжок {m['jump']}), вишлисты ≈{m['est_before']}→{m['est_after']}, "
              f"прирост ≈{m['gain']}")
    print(f"отчёт: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
