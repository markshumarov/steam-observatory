import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import { S } from "./story-i18n.js";

const load = (name) => fetch(`data/${name}`).then((r) => (r.ok ? r.json() : null));
const [story, fests] = await Promise.all([load("story.json"), load("fests.json")]);

const saved = localStorage.getItem("sobs-lang");
let lang = saved === "ru" || saved === "en" ? saved : "en";
const t = (key, vars) => {
  let s = (S[lang] && S[lang][key]) ?? S.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(v);
  return s;
};
const fmt = (n) => new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US").format(n ?? 0);
const el = (sel) => document.querySelector(sel);
// «не посчитать» бывает двух видов: демо вообще нет в топе вишлистов, либо оно
// там есть, но изменения позиции нет — эти категории можно скрыть по отдельности
let showNoRank = true;
let showNoJump = true;

const T = {
  text: "#e8edf7",
  muted: "#8a97ae",
  grid: "#232c3d",
  accent: "#6b9bff",
  accent2: "#38bdf8",
  warn: "#f2a33c",
};
const theme = {
  style: {
    background: "transparent",
    color: T.text,
    fontSize: "12.5px",
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif",
    overflow: "visible",
  },
  color: { scheme: "tableau10" },
};
const plot = (spec) => Plot.plot({ ...theme, ...spec });

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const short = (f) => {
  const m = f.season === "winter" ? 1 : f.season === "summer" ? 5 : 9;
  return `${MONTHS[m]} ${String(f.year).slice(2)}`;
};
const festOf = (slug) => (fests || []).find((f) => f.slug === slug) || { slug, year: 2026, season: "autumn" };

function applyStatic() {
  document.documentElement.lang = lang;
  document.title = lang === "ru"
    ? "Steam Observatory — что говорят цифры Next Fest"
    : "Steam Observatory — what the Next Fest numbers say";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.innerHTML = t(node.dataset.i18n);
  }
  el("#footer").textContent = t("footer", { year: new Date().getFullYear() });
  for (const b of document.querySelectorAll(".lang button")) {
    b.classList.toggle("on", b.dataset.lang === lang);
  }
}

// --- источники ----------------------------------------------------------
function renderSources() {
  el("#sources").innerHTML = `
  <table>
    <thead><tr><th>${t("th_source")}</th><th>${t("what")}</th><th>${t("note")}</th></tr></thead>
    <tbody>
      ${(story.attribution || [])
        .map(
          (s) => `<tr>
        <td><a href="${s.url}" target="_blank" rel="noopener">${s.name}</a></td>
        <td>${s.what}</td>
        <td class="mono">${s.note}</td>
      </tr>`
        )
        .join("")}
    </tbody>
  </table>`;
}

// --- 0. Тиры вишлистов --------------------------------------------------
function renderTiers() {
  const block = story.tiers || {};
  const tiers = block.tiers || [];
  if (!tiers.length) return;
  const total = block.total || tiers.reduce((sum, x) => sum + x.games, 0);
  const pick = (key) => tiers.find((x) => x.key === key) || { games: 0 };
  // Доли считаем от того, что видно на графике: скрывая категории «не посчитать»,
  // пользователь меняет знаменатель — проценты всегда складываются в 100%
  const cov = block.coverage || {};
  const lineup = cov.lineup || total;
  const inChart = cov.in_chart || total;
  const noRank = cov.no_rank ?? Math.max(0, lineup - inChart);
  const noJump = cov.no_jump ?? Math.max(0, inChart - total);
  let share = () => "0.0";

  const COLORS = { diamond: "#7dd3fc", gold: "#fbbf24", silver: "#cbd5e1", bronze: "#d97706" };
  const rangeLabel = (x) =>
    x.to == null
      ? `${fmt(x.from)}+`
      : x.from == null
        ? `0–${fmt(x.to)}`
        : `${fmt(x.from)}–${fmt(x.to)}`;

  const rows = tiers.map((x) => ({
    label: `${x.medal} ${x.key[0].toUpperCase()}${x.key.slice(1)} · ${rangeLabel(x)}`,
    games: x.games,
    share: (100 * x.games) / total,
    color: COLORS[x.key] || T.accent,
  }));

  if (showNoJump && noJump) {
    rows.push({ label: t("nojump_bar"), games: noJump, share: 0, color: "#3d4657" });
  }
  if (showNoRank && noRank) {
    rows.push({ label: t("norank_bar"), games: noRank, share: 0, color: "#55607a" });
  }
  const shown = rows.reduce((sum, r) => sum + r.games, 0);
  share = (key) => ((100 * pick(key).games) / shown).toFixed(1);
  el("#k-tiers").textContent = t("tiers_kicker", { share: share("diamond") });
  el("#hint-tiers").innerHTML = t("tiers_hint", {
    total: fmt(total),
    outside: fmt(noRank + noJump),
    lineup: fmt(lineup),
    share: ((100 * total) / shown).toFixed(1),
  });

  el("#chart-tiers").replaceChildren(
    plot({
      height: 250,
      marginLeft: 210,
      marginRight: 96,
      x: { grid: true, label: t("tiers_axis") },
      y: { label: null, domain: rows.map((r) => r.label) },
      marks: [
        Plot.barX(rows, { x: "games", y: "label", fill: "color", tip: true }),
        Plot.text(rows, {
          x: "games",
          y: "label",
          text: (d) => `${fmt(d.games)} · ${d.share.toFixed(1)}%`,
          dx: 6,
          textAnchor: "start",
          fill: T.muted,
          fontSize: 11,
        }),
        Plot.ruleX([0], { stroke: T.grid }),
      ],
    })
  );

  el("#take-tiers").innerHTML = [
    t("tiers_b1", { diamond: fmt(pick("diamond").games), diamond_share: share("diamond") }),
    t("tiers_b2", { silver: fmt(pick("silver").games), silver_share: share("silver") }),
    t("tiers_b3", {
      bronze: fmt(pick("bronze").games),
      bronze_share: share("bronze"),
      negatives: fmt(block.negatives),
    }),
    t("tiers_b4", {
      edge_below: fmt(block.edge_below),
      edge_above: fmt(block.edge_above),
      share_median: block.share_median,
    }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 1. Предложение -----------------------------------------------------
function renderSupply() {
  // Внешнее число (GameDiscoverCo / How To Market A Game) считаем основным:
  // свой пересчёт показываем в подсказке и в выводах, где он расходится.
  const rows = (story.supply || []).map((s) => {
    const f = festOf(s.slug);
    const external = s.theirs ?? null;
    return {
      label: short(f),
      games: external ?? s.games,
      ours: s.games,
      external,
      quality: s.quality || f.quality || "full",
    };
  });
  const first = rows[0]?.games ?? 1;
  const last = rows.at(-1)?.games ?? 1;
  el("#k-supply").textContent = t("supply_kicker", { n: Math.round(last / first) });

  const diffs = rows
    .filter((d) => d.external && d.quality === "full")
    .map((d) => (d.ours / d.external - 1) * 100);
  const lo = diffs.length ? Math.min(...diffs) : null;
  const hi = diffs.length ? Math.max(...diffs) : null;

  el("#chart-supply").replaceChildren(
    plot({
      height: 340,
      marginTop: 16,
      marginLeft: 70,
      marginBottom: 58,
      x: { label: null, tickRotate: -40, domain: rows.map((d) => d.label) },
      y: { grid: true, label: t("supply_games") },
      marks: [
        Plot.barY(rows, {
          x: "label",
          y: "games",
          fill: (d) => (d.external ? T.accent : T.warn),
          tip: true,
        }),
        Plot.text(rows, {
          x: "label",
          y: "games",
          text: (d) => fmt(d.games),
          dy: -6,
          fontSize: 9.5,
          fill: T.muted,
        }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );
  el("#take-supply").innerHTML = [
    t("supply_b1", { now: fmt(last) }),
    t("supply_b2", { now: fmt(last) }),
    t("supply_b4", {
      n: String(rows.filter((d) => d.external).length),
      lo: lo == null ? "—" : `${lo > 0 ? "+" : ""}${lo.toFixed(1)}`,
      hi: hi == null ? "—" : `${hi > 0 ? "+" : ""}${hi.toFixed(1)}`,
      ours: fmt(rows.at(-1)?.ours ?? 0),
    }),
    t("supply_b3"),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 2. Внимание --------------------------------------------------------
function renderAttention() {
  const a = story.attention || {};
  el("#k-attention").textContent = t("attention_kicker", { share: a.top10_share ?? "—" });

  const total = a.sum_all || 1;
  const shares = [
    { label: t("top10"), value: a.sum_top10 || 0 },
    { label: t("next40"), value: (a.sum_top50 || 0) - (a.sum_top10 || 0) },
    { label: t("rest"), value: total - (a.sum_top50 || 0) },
  ].map((d) => ({ ...d, pct: (100 * d.value) / total }));

  el("#chart-attention").replaceChildren(
    plot({
      height: 250,
      marginLeft: 74,
      marginRight: 76,
      x: { grid: true, label: t("chart_board") },
      y: { label: null, domain: shares.map((d) => d.label) },
      marks: [
        Plot.barX(shares, {
          x: "pct",
          y: "label",
          fill: (d, i) => [T.accent, T.accent2, T.muted][i] || T.muted,
          tip: true,
        }),
        Plot.text(shares, {
          x: "pct",
          y: "label",
          text: (d) => `${d.pct.toFixed(1)}%`,
          dx: 6,
          textAnchor: "start",
          fill: T.muted,
          fontSize: 11,
        }),
        Plot.ruleX([0], { stroke: T.grid }),
      ],
    })
  );

  const hist = (a.our_hist || []).map((b) => ({
    label:
      b.to == null ? `${fmt(b.from)}+` : b.from === 0 ? "0" : `${fmt(b.from)}–${fmt(b.to)}`,
    games: b.games,
  }));
  if (hist.length) {
    el("#chart-peaks").replaceChildren(
      plot({
        height: 250,
        marginLeft: 56,
        marginBottom: 52,
        x: { label: null, tickRotate: -35 },
        y: { grid: true, label: t("demos") },
        marks: [
          Plot.barY(hist, { x: "label", y: "games", fill: T.accent2, tip: true }),
          Plot.text(hist, {
            x: "label",
            y: "games",
            text: (d) => fmt(d.games),
            dy: -6,
            fontSize: 10,
            fill: T.muted,
          }),
          Plot.ruleY([0], { stroke: T.grid }),
        ],
      })
    );
  }

  el("#take-attention").innerHTML = [
    t("attention_b1", { share: a.top10_share }),
    t("attention_b2", { median: fmt(a.our_median), dead: fmt(a.our_zero_or_one), games: fmt(a.our_games) }),
    t("attention_b3", { over100: fmt(a.our_ge_100), games: fmt(a.our_games) }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 3. Вишлисты --------------------------------------------------------
function renderWishlists() {
  const c = story.conversion || {};
  const qs = ["p10", "p25", "p50", "p75", "p90"].map((k) => ({
    key: k,
    label: t(`q_${k}`),
    value: (c.per_1k || {})[k],
  }));
  const p50 = (c.per_1k || {}).p50;
  el("#k-wishlists").textContent = p50 ? p50.toFixed(1) : "6.1";
  el("#chart-wishlists").replaceChildren(
    plot({
      height: 280,
      marginTop: 18,
      marginLeft: 64,
      marginBottom: 48,
      x: { label: null },
      y: { grid: true, label: t("per_1k") },
      marks: [
        Plot.barY(qs, {
          x: "label",
          y: "value",
          fill: (d) => (d.key === "p50" ? T.accent : T.accent2),
          tip: true,
        }),
        Plot.text(qs, {
          x: "label",
          y: "value",
          text: (d) => (d.value == null ? "" : d.value.toFixed(1)),
          dy: -6,
          fontSize: 11,
          fill: T.muted,
        }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );
  const spread = p50 && (c.per_1k || {}).p10 ? ((c.per_1k || {}).p90 / (c.per_1k || {}).p10).toFixed(0) : "13";
  el("#take-wishlists").innerHTML = [
    t("wishlists_b1", { p50: p50?.toFixed(1), p10: (c.per_1k || {}).p10, p90: (c.per_1k || {}).p90, spread }),
    t("wishlists_b2", { high: (c.high_wishlists ?? 0).toFixed(1), low: (c.low_wishlists ?? 0).toFixed(1) }),
    t("wishlists_b3", { wl: fmt(c.wishlists_median) }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 4. Cozy ------------------------------------------------------------
function renderCozy() {
  const rows = (story.cozy?.by_year || []).filter((r) => r.releases && r.median_reviews);
  if (!rows.length) return;
  const first = rows[0];
  const last = rows.at(-1);
  const grown = Math.round(last.releases / first.releases);
  el("#k-cozy").textContent = t("cozy_kicker", { grown });

  const data = rows.flatMap((r) => [
    { year: String(r.year), metric: t("cozy_releases"), index: (100 * r.releases) / first.releases },
    { year: String(r.year), metric: t("cozy_reviews"), index: (100 * r.median_reviews) / first.median_reviews },
  ]);

  el("#chart-cozy").replaceChildren(
    plot({
      height: 320,
      marginTop: 18,
      marginLeft: 70,
      marginBottom: 48,
      x: { label: t("year") },
      y: { type: "log", grid: true, label: "index, 2019 = 100" },
      color: { legend: true },
      marks: [
        Plot.line(data, { x: "year", y: "index", stroke: "metric", strokeWidth: 2.5, marker: "circle", tip: true }),
        Plot.ruleY([100], { stroke: T.grid, strokeDasharray: "4 4" }),
      ],
    })
  );

  el("#take-cozy").innerHTML = [
    t("cozy_b1", {
      first_rel: fmt(first.releases),
      last_rel: fmt(last.releases),
      last_year: last.year,
      last_12m: fmt(story.cozy?.released_last_12m),
    }),
    t("cozy_b2", {
      first_rev: fmt(first.median_reviews),
      last_rev: fmt(last.median_reviews),
      grown,
    }),
    t("cozy_b3", {
      share: `${Math.round(100 * (last.share_under_10 || 0))}%`,
      too_fresh: fmt(last.too_fresh),
    }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 5. Выводы ----------------------------------------------------------
// --- 1b. Какая доля вишлистов набрана за фестиваль ----------------------
function renderGains() {
  const b = story.tiers || {};
  const buckets = b.pct_buckets || [];
  if (!buckets.length) return;
  const out = story.outside || {};
  const cov = b.coverage || {};
  const rows = buckets.map((x) => ({ label: x.label, games: x.games }));
  if (cov.outside) {
    rows.push({ label: t("outside_bar"), games: cov.outside, outside: true });
  }
  el("#k-gains").textContent = t("sample_measured", { n: fmt(cov.measured) });
  el("#hint-gains").innerHTML = t("gains_hint", {
    measured: fmt(cov.measured),
    lineup: fmt(cov.lineup),
    outside: fmt(cov.outside),
  });
  el("#chart-gains").replaceChildren(
    plot({
      height: 300,
      marginTop: 16,
      marginLeft: 70,
      marginBottom: 52,
      x: { label: t("gains_legend"), domain: rows.map((d) => d.label), tickRotate: -20 },
      y: { grid: true, label: t("gains_axis") },
      marks: [
        Plot.barY(rows, {
          x: "label",
          y: "games",
          fill: (d) => (d.outside ? "#55607a" : T.accent),
          tip: true,
        }),
        Plot.text(rows, {
          x: "label",
          y: "games",
          text: (d) => fmt(d.games),
          dy: -6,
          fontSize: 9.5,
          fill: T.muted,
        }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );
  el("#take-gains").innerHTML = [
    t("gains_b1", { median: b.share_median, p10: b.share_p10, p90: b.share_p90 }),
    t("gains_b2", { over_half: fmt(b.share_over_half) }),
    t("gains_b3", {
      sampled: fmt(out.sampled),
      with_rank: fmt(out.with_rank),
      trace: ((out.share_with_rank || 0) * 100).toFixed(1),
      median: fmt(out.peaks_sample?.median),
    }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- 1c. С какими вишлистами входили и выходили -------------------------
function renderWl() {
  const b = story.tiers || {};
  const hist = b.wl_hist || [];
  if (!hist.length) return;
  const long = [];
  for (const r of hist) {
    long.push({ bucket: r.label, when: t("wl_before"), value: r.before });
    long.push({ bucket: r.label, when: t("wl_after"), value: r.after });
  }
  el("#chart-wl").replaceChildren(
    plot({
      height: 300,
      marginTop: 16,
      marginLeft: 70,
      marginBottom: 46,
      fx: { label: null },
      x: { label: null },
      y: { grid: true, label: t("wl_axis") },
      color: {
        domain: [t("wl_before"), t("wl_after")],
        range: ["#55607a", T.accent],
        legend: true,
      },
      marks: [
        Plot.barY(long, { fx: "bucket", x: "when", y: "value", fill: "when", tip: true }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );
  const first = hist[0] || {};
  const last = hist[hist.length - 1] || {};
  el("#take-wl").innerHTML = [
    t("wl_b1", { median_before: fmt(b.coverage?.median_before) }),
    t("wl_b2", {
      b1: fmt(first.before),
      b2: fmt(first.after),
      a1: fmt(last.before),
      a2: fmt(last.after),
    }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

// --- переключатель выборки ---------------------------------------------
function setupSwitch() {
  const rank = el("#show-no-rank");
  const jump = el("#show-no-jump");
  if (!rank || !jump) return;
  rank.checked = showNoRank;
  jump.checked = showNoJump;
  const rerender = () => {
    showNoRank = rank.checked;
    showNoJump = jump.checked;
    renderTiers();
  };
  rank.onchange = rerender;
  jump.onchange = rerender;
}

function renderTakeaways() {
  const sup = story.supply || [];
  const g = (slug) => sup.find((s) => s.slug === slug)?.games;
  el("#checklist").innerHTML = [
    t("t1"),
    t("t2"),
    t("t3"),
    t("t4"),
    t("t5", { from: fmt(g("oct2024")), to: fmt(g("oct2026")) }),
  ]
    .map((x) => `<li>${x}</li>`)
    .join("");
}

function renderAll() {
  applyStatic();
  renderTiers();
  renderGains();
  renderWl();
  setupSwitch();
  renderSupply();
  renderAttention();
  renderWishlists();
  renderCozy();
  renderTakeaways();
  renderSources();
}

for (const b of document.querySelectorAll(".lang button")) {
  b.addEventListener("click", () => {
    if (lang === b.dataset.lang) return;
    lang = b.dataset.lang;
    localStorage.setItem("sobs-lang", lang);
    renderAll();
  });
}

renderAll();

