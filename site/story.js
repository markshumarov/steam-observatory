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

// --- 1. Предложение -----------------------------------------------------
function renderSupply() {
  const rows = (story.supply || []).map((s) => {
    const f = festOf(s.slug);
    return { label: short(f), games: s.games, quality: f.quality || "full" };
  });
  const first = rows[0]?.games ?? 1;
  const last = rows.at(-1)?.games ?? 1;
  el("#k-supply").textContent = t("supply_kicker", { n: Math.round(last / first) });
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
          fill: (d) => (d.quality === "full" ? T.accent : T.warn),
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
  el("#take-supply").innerHTML = [t("supply_b1", { now: fmt(last) }), t("supply_b2", { now: fmt(last) }), t("supply_b3")]
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

