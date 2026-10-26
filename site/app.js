import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import { STR } from "./i18n.js";

const load = (name) => fetch(`data/${name}`).then((r) => (r.ok ? r.json() : null));

// Данные грузятся двумя этапами. Сначала маленькие файлы (издания, теги) —
// страница сразу показывает цифры. Тяжёлый ccu.json (7 тысяч демо) идёт вторым
// запросом: пока он в пути, в блоках видны скелетоны, а не пустота.
const [festsRaw, tags, tagCounts] = await Promise.all([
  load("fests.json"),
  load("tags.json"),
  load("tag_counts.json"),
]);
let ccu = null;

// --- язык ---------------------------------------------------------------
// По умолчанию английский; выбор запоминается в localStorage.
const saved = localStorage.getItem("sobs-lang");
let lang = saved === "ru" || saved === "en" ? saved : "en";

const t = (key, vars) => {
  let s = (STR[lang] && STR[lang][key]) ?? STR.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(v);
  return s;
};
const num = () => new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US");
const fmt = (n) => num().format(n ?? 0);
const el = (sel) => document.querySelector(sel);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const fests = (festsRaw ?? []).slice();
const festivalLabel = (f) => (lang === "ru" ? f.label_ru : f.label_en) || f.slug;
const shortLabel = (f) => {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mIdx = f.season === "winter" ? 1 : f.season === "summer" ? 5 : 9;
  return `${months[mIdx]} ${String(f.year).slice(2)}`;
};

// --- тема графиков ------------------------------------------------------
const T = {
  text: "#e8edf7",
  muted: "#8a97ae",
  grid: "#232c3d",
  accent: "#6b9bff",
  accent2: "#38bdf8",
  warn: "#f2a33c",
  danger: "#ef6a6a",
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

// --- статические тексты -------------------------------------------------
function applyStatic() {
  document.documentElement.lang = lang;
  document.title =
    lang === "ru"
      ? "Steam Observatory — Steam Next Fest в цифрах"
      : "Steam Observatory — Steam Next Fest in numbers";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  el("#tag-search").placeholder = t("tags_search");
  el("#ccu-search").placeholder = t("ccu_search");
  el("#footer").textContent = t("footer", { year: new Date().getFullYear() });
  el("#ccu-csv").textContent = t("ccu_csv");
  for (const b of document.querySelectorAll(".lang button")) {
    b.classList.toggle("on", b.dataset.lang === lang);
    b.setAttribute("aria-pressed", b.dataset.lang === lang ? "true" : "false");
  }
  el("#ccu-chart-title").textContent = t("ccu_chart_title", { n: ccuLimitLabel() });
}

function ccuLimitLabel() {
  const v = el("#ccu-limit")?.value || ccuLimit;
  return v === "all" ? t("ccu_all") : v;
}

// --- переключение языка -------------------------------------------------
for (const b of document.querySelectorAll(".lang button")) {
  b.addEventListener("click", () => {
    if (lang === b.dataset.lang) return;
    lang = b.dataset.lang;
    localStorage.setItem("sobs-lang", lang);
    renderAll();
  });
}

// --- 1. Издания ---------------------------------------------------------
function renderEditions() {
  const rows = fests.map((f) => ({
    slug: f.slug,
    label: shortLabel(f),
    final: f.n_final,
    preview: f.n_preview ?? null,
    expected: f.expected ?? null,
    quality: f.quality || "full",
  }));

  el("#chart-editions").replaceChildren(
    plot({
      height: 380,
      marginTop: 18,
      marginLeft: 76,
      marginBottom: 62,
      x: { label: null, tickRotate: -40, domain: rows.map((d) => d.label) },
      y: { grid: true, label: t("y_games"), nice: true },
      marks: [
        Plot.barY(rows, {
          x: "label",
          y: "final",
          fill: (d) => (d.quality === "partial" ? T.warn : T.accent),
          tip: true,
        }),
        Plot.line(
          rows.filter((d) => d.preview != null),
          { x: "label", y: "preview", stroke: T.muted, strokeWidth: 2 }
        ),
        Plot.dot(rows.filter((d) => d.preview != null), {
          x: "label",
          y: "preview",
          r: 2.5,
          fill: T.muted,
        }),
        Plot.dot(rows.filter((d) => d.expected != null), {
          x: "label",
          y: "expected",
          r: 4,
          fill: T.danger,
          tip: true,
        }),
        Plot.text(rows, {
          x: "label",
          y: "final",
          text: (d) => `${d.quality === "full" ? "" : "≥"}${fmt(d.final)}`,
          dy: -7,
          fontSize: 10.5,
          fill: T.muted,
        }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );

  el("#table-editions").innerHTML = `
  <table>
    <thead><tr>
      <th>${t("th_edition")}</th><th>${t("th_final")}</th><th>${t("th_preview")}</th>
      <th>${t("th_control")}</th><th>${t("th_diff")}</th><th>${t("th_source")}</th><th>${t("th_note")}</th>
    </tr></thead>
    <tbody>
      ${fests
        .map((f) => {
          const note = (lang === "ru" ? f.note_ru : f.note_en) || "";
          return `<tr>
        <td>${esc(festivalLabel(f))}${
            f.quality === "partial" ? `<span class="tag-partial">${t("partial")}</span>` : ""
          }</td>
        <td>${f.quality === "partial" ? "≥ " : ""}${fmt(f.n_final)}</td>
        <td>${f.n_preview ? fmt(f.n_preview) : "—"}</td>
        <td>${f.expected ? fmt(f.expected) : "—"}</td>
        <td>${f.diff_pct != null ? (f.diff_pct > 0 ? "+" : "") + f.diff_pct + "%" : "—"}</td>
        <td><code>${esc(f.source)}</code></td>
        <td class="mono">${esc(note)}</td>
      </tr>`;
        })
        .join("")}
    </tbody>
  </table>`;
}

// --- 2. Теги ------------------------------------------------------------
// Тег-серии строим только по полным составам: реконструкции из срезов
// архивной страницы смещены и исказили бы динамику.
const festSlugs = fests
  .filter((f) => tagCounts && tagCounts[f.slug] && f.quality === "full")
  .map((f) => f.slug);
const tagBasis = (f) => f.tag_basis || f.n_final;
const tagById = tags || {};

// максимальная доля тега по всем изданиям — для сортировки и подсказок
const tagPeak = new Map();
for (const slug of festSlugs) {
  const f = fests.find((x) => x.slug === slug);
  for (const [tid, n] of Object.entries(tagCounts[slug] || {})) {
    // без названия остаются только отставленные Steam теги — читателю они не нужны
    if (!tagById[tid]) continue;
    const share = (100 * n) / tagBasis(f);
    const prev = tagPeak.get(tid);
    if (!prev || share > prev.share) tagPeak.set(tid, { n, share });
  }
}
// ВЫБОРКА: все теги, а не топ-14 — в данных их больше четырёхсот
const allTags = [...tagPeak.entries()]
  .sort((a, b) => b[1].share - a[1].share)
  .map(([tid]) => tid);
const tagName = (tid) =>
  tagById[tid] || `${lang === "ru" ? "тег" : "tag"} ${tid}`;
const selected = new Set(allTags.slice(0, 3));
let tagQuery = "";

function renderPicker() {
  const q = tagQuery.trim().toLowerCase();
  const list = q ? allTags.filter((tid) => tagName(tid).toLowerCase().includes(q)) : allTags;
  el("#tag-picker").innerHTML = list.length
    ? list
        .map((tid) => {
          const peak = tagPeak.get(tid);
          return `<button type="button" class="chip" data-tag="${tid}" aria-pressed="${
            selected.has(tid) ? "true" : "false"
          }">${esc(tagName(tid))}<span class="n">${peak.share.toFixed(1)}%</span></button>`;
        })
        .join("")
    : `<span class="empty">${t("ccu_no_results")}</span>`;
  el("#tag-count").textContent =
    t("tags_shown", { shown: list.length, total: allTags.length }) +
    " · " +
    t("tags_selected", { n: selected.size });
  for (const b of el("#tag-picker").querySelectorAll("button")) {
    b.addEventListener("click", () => {
      const tid = b.dataset.tag;
      if (selected.has(tid)) selected.delete(tid);
      else selected.add(tid);
      renderPicker();
      renderTags();
    });
  }
}

function renderTags() {
  const chart = el("#chart-tags");
  if (!selected.size) {
    chart.innerHTML = `<p class="empty">${t("tags_selected", { n: 0 })}</p>`;
    return;
  }
  const rows = [];
  for (const slug of festSlugs) {
    const f = fests.find((x) => x.slug === slug);
    for (const tid of selected) {
      const n = (tagCounts[slug] || {})[tid];
      if (!n) continue; // издание без этого тега — линия просто рвётся
      rows.push({
        label: shortLabel(f),
        tag: tagName(tid),
        share: (100 * n) / tagBasis(f),
        n,
      });
    }
  }
  chart.replaceChildren(
    plot({
      height: 390,
      marginLeft: 62,
      marginBottom: 56,
      x: {
        label: null,
        tickRotate: -40,
        domain: festSlugs.map((s) => shortLabel(fests.find((f) => f.slug === s))),
      },
      y: { grid: true, label: t("tags_y"), zero: true },
      color: { legend: true },
      marks: [
        Plot.line(rows, {
          x: "label",
          y: "share",
          stroke: "tag",
          strokeWidth: 2,
          marker: "circle",
          tip: true,
        }),
        Plot.ruleY([0], { stroke: T.grid }),
      ],
    })
  );
}

function renderCompare() {
  const festA = el("#fest-a");
  const festB = el("#fest-b");
  const keepA = festA.value;
  const keepB = festB.value;
  festA.innerHTML = "";
  festB.innerHTML = "";
  for (const slug of festSlugs) {
    const f = fests.find((x) => x.slug === slug);
    festA.append(new Option(festivalLabel(f), slug));
    festB.append(new Option(festivalLabel(f), slug));
  }
  festA.value = keepA || festSlugs.at(-1);
  festB.value = keepB || festSlugs.at(-2);

  const a = festA.value;
  const b = festB.value;
  const fa = fests.find((x) => x.slug === a);
  const fb = fests.find((x) => x.slug === b);
  const ma = tagCounts[a] ?? {};
  const mb = tagCounts[b] ?? {};
  const ids = new Set([...Object.keys(ma), ...Object.keys(mb)]);
  const rows = [...ids]
    .map((tid) => {
      const sa = (100 * (ma[tid] ?? 0)) / tagBasis(fa);
      const sb = (100 * (mb[tid] ?? 0)) / tagBasis(fb);
      return { name: tagName(tid), sa, sb, d: sa - sb };
    })
    .sort((x, y) => Math.abs(y.d) - Math.abs(x.d))
    .slice(0, 15);

  el("#table-tags").innerHTML = `
  <table>
    <thead><tr><th>${t("th_tag")}</th><th>${esc(festivalLabel(fa))}</th><th>${esc(
    festivalLabel(fb)
  )}</th><th>${t("th_change")}</th></tr></thead>
    <tbody>
      ${rows
        .map(
          (r) => `<tr>
        <td>${esc(r.name)}</td>
        <td>${r.sa.toFixed(1)}%</td>
        <td>${r.sb.toFixed(1)}%</td>
        <td>${(r.d > 0 ? "+" : "") + r.d.toFixed(1)}</td>
      </tr>`
        )
        .join("")}
    </tbody>
  </table>`;
}

// --- 3. Игроки в демо ---------------------------------------------------
let ccuQuery = "";
let ccuSort = "peak-desc";
let ccuLimit = "25";
let ccuAll = [];
let stats = {};
const gameLabel = (d) => d.name || `appid ${d.demo_appid}`;

function setCcu(data) {
  ccu = data;
  ccuAll = data && data.top ? data.top.slice() : [];
  stats = (data && data.stats) || {};
}

function buildCcuControls() {
  const sortSel = el("#ccu-sort");
  sortSel.innerHTML = "";
  const sorts = [
    ["peak-desc", "sort_peak_desc"],
    ["peak-asc", "sort_peak_asc"],
    ["name", "sort_name"],
  ];
  for (const [value, key] of sorts) sortSel.append(new Option(t(key), value));
  sortSel.value = ccuSort;

  const limSel = el("#ccu-limit");
  limSel.innerHTML = "";
  for (const value of ["10", "25", "50", "100", "all"]) {
    limSel.append(new Option(value === "all" ? t("ccu_all") : t("ccu_top", { n: value }), value));
  }
  limSel.value = ccuLimit;

  sortSel.onchange = () => {
    ccuSort = sortSel.value;
    renderCcu();
  };
  limSel.onchange = () => {
    ccuLimit = limSel.value;
    renderCcu();
  };
  el("#ccu-search").oninput = (e) => {
    ccuQuery = e.target.value;
    renderCcu();
  };
}

function filteredCcu() {
  const q = ccuQuery.trim().toLowerCase();
  const rows = q
    ? ccuAll.filter(
        (d) =>
          gameLabel(d).toLowerCase().includes(q) || String(d.demo_appid).includes(q) ||
          String(d.base_appid || "").includes(q)
      )
    : ccuAll.slice();
  if (ccuSort === "name") rows.sort((a, b) => gameLabel(a).localeCompare(gameLabel(b)));
  else if (ccuSort === "peak-asc") rows.sort((a, b) => a.peak - b.peak);
  else rows.sort((a, b) => b.peak - a.peak);
  return rows;
}

function renderCcu() {
  if (!ccu) return; // данные ещё в пути — в блоках остаются скелетоны
  const kpis = [
    [fmt(stats.samples ?? 0), "kpi_samples"],
    [fmt(stats.games ?? ccuAll.length), "kpi_demos"],
    [fmt(stats.median ?? 0), "kpi_median"],
    [fmt(stats.ge100 ?? 0), "kpi_100"],
  ];
  el("#kpis").innerHTML = kpis
    .map(([v, k]) => `<div class="kpi"><div class="v">${v}</div><div class="k">${t(k)}</div></div>`)
    .join("");

  // распределение пиков: сколько демо попало в каждый диапазон
  const hist = (stats.hist || []).map((b) => ({
    label: b.to == null ? `${fmt(b.from)}+` : b.from === 0 ? "0" : `${fmt(b.from + 1)}–${fmt(b.to)}`,
    games: b.games,
  }));
  if (hist.length) {
    el("#chart-hist").replaceChildren(
      plot({
        height: 300,
        marginLeft: 56,
        marginBottom: 54,
        x: { label: null, tickRotate: -35 },
        y: { grid: true, label: t("hist_y") },
        marks: [
          Plot.barY(hist, { x: "label", y: "games", fill: T.accent2, tip: true }),
          Plot.text(hist, {
            x: "label",
            y: "games",
            text: (d) => fmt(d.games),
            dy: -7,
            fill: T.muted,
            fontSize: 11,
          }),
          Plot.ruleY([0], { stroke: T.grid }),
        ],
      })
    );
  }

  // топ демо: показываем выбранное число, но поиск идёт по всему списку
  const rows = filteredCcu();
  const slice = ccuLimit === "all" ? 200 : Number(ccuLimit);
  const top = rows.slice(0, slice).map((d, i) => ({
    ...d,
    label: `${i + 1}. ${gameLabel(d)}`,
  }));
  el("#ccu-chart-title").textContent = t("ccu_chart_title", {
    n: ccuLimit === "all" ? fmt(rows.length) : fmt(top.length),
  });

  if (!top.length) {
    el("#chart-ccu").innerHTML = `<p class="empty">${t("ccu_no_results")}</p>`;
  } else {
    el("#chart-ccu").replaceChildren(
      plot({
        height: Math.max(240, top.length * 21 + 50),
        marginLeft: 320,
        marginRight: 70,
        x: { grid: true, label: t("th_peak") },
        y: {
          label: null,
          domain: top.map((d) => d.label),
          tickFormat: (d) => (d.length > 44 ? `${d.slice(0, 42)}…` : d),
        },
        marks: [
          Plot.barX(top, { x: "peak", y: "label", fill: T.accent, tip: true }),
          Plot.text(top, {
            x: "peak",
            y: "label",
            text: (d) => fmt(d.peak),
            dx: 6,
            textAnchor: "start",
            fill: T.muted,
            fontSize: 11,
          }),
          Plot.ruleX([0], { stroke: T.grid }),
        ],
      })
    );
  }

  // полная таблица: все найденные игры, а не только вершина списка
  const MAX_ROWS = 2000;
  const tableRows = rows.slice(0, MAX_ROWS);
  el("#table-ccu").innerHTML = tableRows.length
    ? `<table>
    <thead><tr><th>${t("th_rank")}</th><th>${t("th_game")}</th><th>${t("th_peak")}</th><th>${t("th_appid")}</th></tr></thead>
    <tbody>
      ${tableRows
        .map((d, i) => {
          const appid = d.base_appid || d.demo_appid;
          return `<tr>
        <td>${i + 1}</td>
        <td><a href="https://store.steampowered.com/app/${appid}/" target="_blank" rel="noopener">${esc(
            gameLabel(d)
          )}</a></td>
        <td>${fmt(d.peak)}</td>
        <td class="mono">${appid}</td>
      </tr>`;
        })
        .join("")}
    </tbody>
  </table>
  ${rows.length > MAX_ROWS ? `<p class="hint">${t("ccu_table_note", { n: fmt(MAX_ROWS) })}</p>` : ""}`
    : `<p class="empty">${t("ccu_no_results")}</p>`;
}

function renderAll() {
  applyStatic();
  renderEditions();
  renderTags();
  renderCompare();
  buildCcuControls();
  renderCcu();
}

// --- запуск -------------------------------------------------------------
el("#tag-search").addEventListener("input", (e) => {
  tagQuery = e.target.value;
  renderPicker();
});
el("#tag-clear").addEventListener("click", () => {
  selected.clear();
  renderPicker();
  renderTags();
});
el("#fest-a").addEventListener("change", renderCompare);
el("#fest-b").addEventListener("change", renderCompare);

renderAll();
renderPicker();

// --- этап 2: тяжёлые данные по демо ------------------------------------
(async () => {
  const status = el("#ccu-status");
  status.hidden = false;
  status.textContent = t("loading");
  const data = await load("ccu.json");
  if (!data) {
    status.textContent = t("load_error");
    for (const sel of ["#kpis", "#chart-hist", "#chart-ccu", "#table-ccu"]) {
      el(sel).innerHTML = "";
    }
    return;
  }
  setCcu(data);
  status.hidden = true;
  buildCcuControls();
  renderCcu();
})();

