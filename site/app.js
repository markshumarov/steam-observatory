import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";

const load = (name) => fetch("data/" + name).then((r) => r.json());
const [fests, tags, tagCounts, ccu] = await Promise.all([
  load("fests.json"),
  load("tags.json"),
  load("tag_counts.json"),
  load("ccu.json"),
]);

const fmt = new Intl.NumberFormat("ru-RU");
const el = (sel) => document.querySelector(sel);
const label = (slug) => {
  const f = fests.find((x) => x.slug === slug);
  return f ? `${f.label_ru} ${f.year}` : slug;
};

// --- 1. Издания ---------------------------------------------------------
const editionRows = fests.map((f) => ({
  slug: f.slug,
  final: f.n_final,
  preview: f.n_preview ?? null,
  expected: f.expected ?? null,
}));

el("#chart-editions").append(
  Plot.plot({
    height: 380,
    marginLeft: 70,
    marginBottom: 80,
    x: { label: null, tickRotate: -40, domain: fests.map((f) => f.slug) },
    y: { grid: true, label: "игр в составе" },
    marks: [
      Plot.barY(editionRows, { x: "slug", y: "final", fill: "#2b6cb0", tip: true }),
      Plot.line(
        editionRows.filter((d) => d.preview != null),
        { x: "slug", y: "preview", stroke: "#8a94a6", strokeWidth: 2, marker: "circle", tip: true }
      ),
      Plot.dot(
        editionRows.filter((d) => d.expected != null),
        { x: "slug", y: "expected", r: 4, fill: "#e53e3e", tip: true }
      ),
      Plot.ruleY([0]),
    ],
  })
);

el("#table-editions").innerHTML = `
<table>
  <thead><tr>
    <th>Издание</th><th>Финал</th><th>Регистрации</th><th>Контроль</th><th>Расхождение</th><th>Источник</th><th>Примечание</th>
  </tr></thead>
  <tbody>
    ${fests
      .map(
        (f) => `<tr>
      <td>${label(f.slug)}</td>
      <td>${fmt.format(f.n_final)}</td>
      <td>${f.n_preview ? fmt.format(f.n_preview) : "—"}</td>
      <td>${f.expected ? fmt.format(f.expected) : "—"}</td>
      <td>${f.diff_pct != null ? (f.diff_pct > 0 ? "+" : "") + f.diff_pct + "%" : "—"}</td>
      <td><code>${f.source}</code></td>
      <td>${f.note ?? ""}</td>
    </tr>`
      )
      .join("")}
  </tbody>
</table>`;

// --- 2. Теги ------------------------------------------------------------
const festSlugs = fests.filter((f) => tagCounts[f.slug]).map((f) => f.slug);
const totals = new Map();
for (const slug of festSlugs) {
  for (const [tid, n] of Object.entries(tagCounts[slug])) {
    totals.set(tid, Math.max(totals.get(tid) ?? 0, n));
  }
}
const topTags = [...totals.entries()]
  .sort((a, b) => b[1] - a[1])
  .slice(0, 14)
  .map(([tid]) => tid);
const selected = new Set(topTags.slice(0, 3));
const tagName = (tid) => tags[tid] ?? "tagid " + tid;

function renderPicker() {
  el("#tag-picker").innerHTML = topTags
    .map(
      (tid) =>
        `<button class="chip" data-tag="${tid}" aria-pressed="${
          selected.has(tid) ? "true" : "false"
        }">${tagName(tid)}</button>`
    )
    .join("");
  for (const b of el("#tag-picker").querySelectorAll("button")) {
    b.addEventListener("click", () => {
      const tid = b.dataset.tag;
      selected.has(tid) ? selected.delete(tid) : selected.add(tid);
      renderPicker();
      renderTags();
    });
  }
}

function renderTags() {
  const rows = [];
  for (const slug of festSlugs) {
    const f = fests.find((x) => x.slug === slug);
    for (const tid of selected) {
      const n = tagCounts[slug][tid];
      if (!n) continue;
      rows.push({ slug, tag: tagName(tid), share: (100 * n) / f.n_final, n });
    }
  }
  el("#chart-tags").replaceChildren(
    Plot.plot({
      height: 360,
      marginLeft: 60,
      marginBottom: 80,
      x: { label: null, tickRotate: -40, domain: festSlugs },
      y: { grid: true, label: "доля участников, %" },
      color: { legend: true },
      marks: [
        Plot.line(rows, { x: "slug", y: "share", stroke: "tag", marker: "circle", tip: true }),
        Plot.ruleY([0]),
      ],
    })
  );
}

// --- сравнение двух изданий --------------------------------------------
const festA = el("#fest-a");
const festB = el("#fest-b");
for (const slug of festSlugs) {
  festA.append(new Option(label(slug), slug));
  festB.append(new Option(label(slug), slug));
}
festA.value = festSlugs.at(-1);
festB.value = festSlugs.at(-2);

function renderCompare() {
  const a = festA.value;
  const b = festB.value;
  const fa = fests.find((x) => x.slug === a);
  const fb = fests.find((x) => x.slug === b);
  const ma = tagCounts[a] ?? {};
  const mb = tagCounts[b] ?? {};
  const ids = new Set([...Object.keys(ma), ...Object.keys(mb)]);
  const rows = [...ids]
    .map((tid) => {
      const sa = (100 * (ma[tid] ?? 0)) / fa.n_final;
      const sb = (100 * (mb[tid] ?? 0)) / fb.n_final;
      return { name: tagName(tid), sa, sb, d: sa - sb };
    })
    .sort((x, y) => Math.abs(y.d) - Math.abs(x.d))
    .slice(0, 15);

  el("#table-tags").innerHTML = `
  <table>
    <thead><tr><th>Тег</th><th>${label(a)}</th><th>${label(b)}</th><th>изм., п.п.</th></tr></thead>
    <tbody>
      ${rows
        .map(
          (r) => `<tr>
        <td>${r.name}</td>
        <td>${r.sa.toFixed(1)}%</td>
        <td>${r.sb.toFixed(1)}%</td>
        <td>${(r.d > 0 ? "+" : "") + r.d.toFixed(1)}</td>
      </tr>`
        )
        .join("")}
    </tbody>
  </table>`;
}
festA.addEventListener("change", renderCompare);
festB.addEventListener("change", renderCompare);

// --- 3. Игроки в демо ---------------------------------------------------
const top = (ccu.top ?? []).slice(0, 20);
el("#ccu-meta").textContent =
  `замеров CCU: ${fmt.format(ccu.samples ?? 0)}; демо с данными: ${fmt.format(ccu.games ?? 0)}`;

if (top.length) {
  el("#chart-ccu").append(
    Plot.plot({
      height: 460,
      marginLeft: 320,
      x: { grid: true, label: "пик игроков в демо" },
      y: { label: null, domain: top.map((d) => d.name || "appid " + d.demo_appid) },
      marks: [
        Plot.barX(top, {
          x: "peak",
          y: (d) => d.name || "appid " + d.demo_appid,
          fill: "#2b6cb0",
          tip: true,
        }),
        Plot.ruleX([0]),
      ],
    })
  );
} else {
  el("#chart-ccu").textContent = "данные по игрокам ещё собираются";
}

renderPicker();
renderTags();
renderCompare();
