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

# тиры How To Market A Game по вишлистам, набранным за фестиваль
gains_file = CACHE / "wishlist_gains.json"
tiers_block = None
if gains_file.exists():
    gains_data = json.loads(gains_file.read_text(encoding="utf-8"))
    rows_all = gains_data.get("all") or []

    # доля прироста от текущего числа вишлистов: сколько «съел» фестиваль
    pct_defs = [(None, 0.0, "<0%"), (0.0, 5.0, "0–5%"), (5.0, 10.0, "5–10%"),
                (10.0, 25.0, "10–25%"), (25.0, 50.0, "25–50%"), (50.0, None, "50%+")]
    shares = sorted(g["gain"] / g["wl_est"] * 100 for g in rows_all if g.get("wl_est"))
    pct_buckets = [
        {
            "label": label,
            "games": sum(1 for s in shares
                         if (lo is None or s >= lo) and (hi is None or s < hi)),
        }
        for lo, hi, label in pct_defs
    ]

    # распределение по числу вишлистов до и после фестиваля.
    # Нижняя граница не 0: кривая «место → вишлисты» у PlayRecon начинается
    # примерно с 6 700 вишлистов, ниже модель просто не видит игры
    wl_defs = [(6_000, 10_000, "6 000–9 999"), (10_000, 25_000, "10 000–24 999"),
               (25_000, 50_000, "25 000–49 999"), (50_000, 100_000, "50 000–99 999"),
               (100_000, None, "100 000+")]

    def _hit(value, lo, hi):
        return value is not None and value >= lo and (hi is None or value < hi)

    wl_hist = [
        {
            "label": label,
            "before": sum(1 for g in rows_all if _hit(g.get("wl_est_before"), lo, hi)),
            "after": sum(1 for g in rows_all if _hit(g.get("wl_est"), lo, hi)),
        }
        for lo, hi, label in wl_defs
    ]

    tiers_block = {
        "tiers": gains_data.get("tiers"),
        "negatives": gains_data.get("tier_negatives"),
        "edge_below": gains_data.get("edge_below"),
        "edge_above": gains_data.get("edge_above"),
        "share_median": gains_data.get("share_median"),
        "share_over_half": gains_data.get("share_over_half"),
        "total": gains_data.get("rows_with_jump"),
        "median_gain": gains_data.get("median_gain"),
        "total_gain": gains_data.get("total_gain_top1000"),
        "corr_players": gains_data.get("corr_gain_vs_players"),
        "quiet_top25": gains_data.get("top25_quiet"),
        "source": "PlayRecon fest board; tier thresholds from How To Market A Game",
        "pct_buckets": pct_buckets,
        "wl_hist": wl_hist,
        "share_p10": int(round(shares[len(shares) // 10])) if shares else None,
        "share_p90": int(round(shares[9 * len(shares) // 10])) if shares else None,
    }

# составы берём из site/data/fests.json: его пишет build_site_data.py из свежего
# датасета, а analysis_outcomes.json может отставать — из-за этого на графике
# составов висели старые числа (598 вместо 708) и не было февраля 2025
fests_file = SITE / "fests.json"
fests_final: dict[str, int] = {}
fests_rows: dict[str, dict] = {}
if fests_file.exists():
    for row in json.loads(fests_file.read_text(encoding="utf-8")):
        fests_rows[row["slug"]] = row
        if row.get("n_final"):
            fests_final[row["slug"]] = row["n_final"]
    stale = [
        f"{s}: fests.json {n}, outcomes {(outcomes['editions'].get(s) or {}).get('n')}"
        for s, n in fests_final.items()
        if (outcomes["editions"].get(s) or {}).get("n") not in (None, n)
    ]
    if stale:
        print("ВНИМАНИЕ: analysis_outcomes.json отстал от fests.json, пересоберите его:")
        for line in stale:
            print("  " + line)


def fest_games(slug: str) -> int | None:
    if slug in fests_final:
        return fests_final[slug]
    return (outcomes["editions"].get(slug) or {}).get("n")


supply_slugs = list(fests_final) or list(outcomes.get("editions", {}))

if tiers_block is not None:
    # сколько демо фестиваля вообще попало в измеримую выборку
    lineup = fests_final.get("oct2026")
    measured = tiers_block.get("total") or 0
    tiers_block["coverage"] = {
        "lineup": lineup,
        "measured": measured,
        "in_chart": (gains_data or {}).get("rows_with_wishlists") or measured,
        "outside": (lineup - measured) if lineup else None,
        "floor": min((g.get("wl_est") or 0) for g in rows_all) if rows_all else None,
        "median_before": sorted(g["wl_est_before"] for g in rows_all
                                if g.get("wl_est_before"))[len(rows_all) // 2]
        if rows_all else None,
    }

    in_chart = (gains_data or {}).get("rows_with_wishlists") or measured
    tiers_block["coverage"]["no_jump"] = max(0, in_chart - measured)
    tiers_block["coverage"]["no_rank"] = max(0, (lineup or 0) - in_chart)

# результат случайной выборки вне борда (scripts/aggregate_outside_sample.py)
outside_report = CACHE / "outside_sample_report.json"
outside_block = None
if outside_report.exists():
    rep = json.loads(outside_report.read_text(encoding="utf-8"))
    outside_block = {
        "sampled": rep.get("sampled"),
        "with_rank": rep.get("with_wishlist_rank"),
        "share_with_rank": rep.get("share_with_rank"),
        "projected": rep.get("projected_with_rank"),
        "no_trace": rep.get("no_wishlist_trace"),
        "outside_board": rep.get("outside_board"),
        "peaks_sample": rep.get("peaks_sample"),
        "peaks_board": rep.get("peaks_board"),
        "gains": [m.get("gain") for m in (rep.get("measured") or [])],
    }

publish = {
    "as_of": "2026-10-26",
    "tiers": tiers_block,
    "outside": outside_block,
    "supply": [
        {
            "slug": slug,
            "games": fest_games(slug),
            # внешнее число (GameDiscoverCo / How To Market A Game) — ему и доверяем
            "theirs": (fests_rows.get(slug) or {}).get("expected"),
            "quality": (fests_rows.get(slug) or {}).get("quality"),
        }
        for slug in supply_slugs
    ],
    "editions": [
        {
            "slug": slug,
            "games": fest_games(slug),
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

