"""Свести данные PlayRecon и наши в один файл для будущих сюжетов.

Кладём в data/cache (папка в .gitignore): данные PlayRecon — коммерческий
источник, публиковать их на сайте можно только после проверки условий.

Запуск: python scripts/build_story_data.py
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
SITE = ROOT / "site" / "data"
OUT = CACHE / "story_data.json"


def structured(pattern: str) -> dict:
    files = sorted(glob.glob(str(CACHE / pattern)))
    if not files:
        return {}
    raw = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    return (raw.get("result") or {}).get("structuredContent") or {}


story: dict = {"sources": {}, "blocks": {}}

# --- 1. ниша Cozy: рост предложения против падения внимания -----------------
niche = structured("playrecon_market_niche_*.json")
nd = niche.get("data") or {}
if nd:
    story["sources"]["niche"] = {
        "tool": "market_niche",
        "tag": nd.get("tag"),
        "match": nd.get("match"),
        "as_of": niche.get("as_of"),
        "note": "reviews window: released 3 years..90 days ago, failures included",
    }
    story["blocks"]["cozy"] = {
        "released": nd.get("released"),
        "releasedLast12m": nd.get("releasedLast12m"),
        "announced": nd.get("announced"),
        "medianPrice": nd.get("medianPrice"),
        "outcomes": nd.get("outcomes"),
        "byYear": nd.get("byYear"),
    }

# --- 2. фестиваль: концентрация внимания и вишлисты -------------------------
board = structured("playrecon_nextfest_live*.json")
bd = board.get("data") or {}
rows = bd.get("rows") or []
if rows:
    peaks = sorted((int(r["peak"]) for r in rows if r.get("peak")), reverse=True)
    story["sources"]["board"] = {
        "tool": "nextfest_live",
        "as_of": board.get("as_of"),
        "fest": bd.get("fest"),
        "boardAt": bd.get("boardAt"),
        "note": "peak = demo peak players since the fest started; wlEst = estimated wishlists",
    }
    story["blocks"]["board"] = {
        "lineup": bd.get("lineup"),
        "rows": len(rows),
        "sum_peak": sum(peaks),
        "top10_share": round(100 * sum(peaks[:10]) / sum(peaks), 1) if peaks else None,
        "median_peak": peaks[len(peaks) // 2] if peaks else None,
        "max_peak": peaks[0] if peaks else None,
        "min_peak": peaks[-1] if peaks else None,
        "games": [
            {
                "name": r.get("name"),
                "appid": r.get("appid"),
                "demo": r.get("demo"),
                "peak": r.get("peak"),
                "now": r.get("now"),
                "wlEst": r.get("wlEst"),
                "wlRankNow": r.get("wl"),
                "wlRankBefore": r.get("wlBefore"),
                "rank": r.get("rank"),
                "tags": (r.get("tags") or [])[:6],
            }
            for r in rows
        ],
    }

# наши собственные замеры CCU по всем демо
ccu_path = SITE / "ccu.json"
if ccu_path.exists():
    ccu = json.loads(ccu_path.read_text(encoding="utf-8"))
    story["sources"]["our_ccu"] = {
        "source": "Steam GetNumberOfCurrentPlayers, own polling",
        "samples": ccu.get("samples"),
        "games": ccu.get("games"),
    }
    story["blocks"]["our_ccu"] = ccu.get("stats")

# --- 3. конверсия вишлистов -------------------------------------------------
conv = structured("playrecon_cohort_wishlist_conversion_*.json")
cd = conv.get("data") or {}
if cd:
    story["sources"]["conversion"] = {
        "tool": "cohort_wishlist_conversion",
        "as_of": conv.get("as_of"),
        "coverage": conv.get("coverage"),
        "note": "reviews in first age_days days per 1000 wishlists estimated at T-days_before",
    }
    story["blocks"]["conversion"] = {
        "days_before": cd.get("days_before"),
        "age_days": cd.get("age_days"),
        "rows": cd.get("rows"),
    }

# --- публикуемая витрина ---------------------------------------------------
# Только то, что идёт на страницу, с явной атрибуцией источников.
outcomes = json.loads((ROOT / "data" / "processed" / "analysis_outcomes.json").read_text(encoding="utf-8"))
full_editions = ["jun2021", "oct2024", "jun2025", "oct2025", "feb2026", "jun2026"]
cozy_rows = [r for r in (story.get("blocks", {}).get("cozy", {}).get("byYear") or [])
             if r.get("year") and r.get("year") >= 2019]
conv_row = ((story.get("blocks", {}).get("conversion", {}).get("rows") or [{}])[0])
board = story.get("blocks", {}).get("board", {})
our_ccu = story.get("blocks", {}).get("our_ccu", {})
board_peaks = sorted([(r.get("peak") or 0) for r in board.get("games") or []], reverse=True)

publish = {
    "as_of": "2026-10-26",
    "supply": [
        {"slug": slug, "games": (outcomes["editions"].get(slug) or {}).get("n")}
        for slug in outcomes.get("editions", {})
    ],
    "editions": [
        {
            "slug": slug,
            "games": (outcomes["editions"].get(slug) or {}).get("n"),
            "median_copies": (outcomes["editions"].get(slug) or {}).get("copies_median"),
            "share_under_1000": (outcomes["editions"].get(slug) or {}).get("share_copies_under_1000"),
            "share_no_reviews": (outcomes["editions"].get(slug) or {}).get("share_no_reviews"),
            "months": (outcomes["editions"].get(slug) or {}).get("months_since_release_median"),
        }
        for slug in full_editions
    ],
    "attention": {
        "lineup": board.get("lineup"),
        "rows": board.get("rows"),
        "top10_share": board.get("top10_share"),
        "sum_top10": sum(board_peaks[:10]),
        "sum_top50": sum(board_peaks[:50]),
        "sum_all": sum(board_peaks),
        "median_peak_top200": board.get("median_peak"),
        "max_peak": board.get("max_peak"),
        "our_games": our_ccu.get("games"),
        "our_median": our_ccu.get("median"),
        "our_zero_or_one": (our_ccu.get("hist") or [{}])[0].get("games"),
        "our_ge_100": our_ccu.get("ge100"),
        "our_hist": our_ccu.get("hist"),
        "top": (board.get("games") or [])[:12],
    },
    "conversion": {
        "n": conv_row.get("n"),
        "wishlists_median": conv_row.get("median_wishlists"),
        "per_1k": {
            "p10": conv_row.get("reviews_per_1k_p10"),
            "p25": conv_row.get("reviews_per_1k_p25"),
            "p50": conv_row.get("reviews_per_1k_p50"),
            "p75": conv_row.get("reviews_per_1k_p75"),
            "p90": conv_row.get("reviews_per_1k_p90"),
        },
        "high_wishlists": conv_row.get("median_if_wishlists_high"),
        "low_wishlists": conv_row.get("median_if_wishlists_low"),
        "age_days": story.get("blocks", {}).get("conversion", {}).get("age_days"),
    },
    "cozy": {
        "released": story.get("blocks", {}).get("cozy", {}).get("released"),
        "released_last_12m": story.get("blocks", {}).get("cozy", {}).get("releasedLast12m"),
        "by_year": [
            {
                "year": r.get("year"),
                "releases": r.get("releases"),
                "median_reviews": r.get("medianReviews"),
                "share_under_10": r.get("shareUnder10Reviews"),
                "too_fresh": r.get("tooFreshToJudge"),
            }
            for r in cozy_rows
        ],
        "share_under_10": (story.get("blocks", {}).get("cozy", {}).get("outcomes") or {}).get("shareUnder10Reviews"),
    },
    "attribution": [
        {"name": "PlayRecon", "what": "wishlist estimates, demo board, niche statistics, "
                                              "wishlist-to-reviews conversion", "url": "https://app.playrecon.com",
         "note": "MCP API; wishlist model is marked experimental; numbers as of 2026-10-26"},
        {"name": "Gamalytic", "what": "copies sold, review score, release dates, tags",
         "url": "https://gamalytic.com", "note": "estimate, not Valve's data"},
        {"name": "Internet Archive", "what": "historical Next Fest lineups",
         "url": "https://web.archive.org", "note": "Wayback snapshots of the festival page"},
        {"name": "Steam", "what": "demo concurrent players, current lineups",
         "url": "https://store.steampowered.com", "note": "public API, own polling"},
    ],
}

out_path = SITE / "story.json"
out_path.write_text(json.dumps(publish, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"витрина: {out_path} ({out_path.stat().st_size} байт)")

