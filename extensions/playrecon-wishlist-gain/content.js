/* PlayRecon wishlist gain — добавляет колонку с оценкой прироста вишлистов
   за фестиваль и сортировку по ней.

   Как считается: в колонке Wishlists страница показывает место в топе вишлистов
   сейчас (#75), прыжок за фестиваль (▲45) и оценку вишлистов (≈733K). Место до
   фестиваля = 75 + 45; сколько вишлистов было на том месте — берём по кривой
   «место → вишлисты», построенной по этой же таблице. Разница — оценка прироста.

   Оценка приблизительная: у PlayRecon модели вишлистов погрешность ±20–30%,
   а места в топе относительные. */

(() => {
  const WL_RE =
    /#([\d\s,]+)(?:([\u25b2\u25bc])\s*([\d\s,]+))?\s*\u2248\s*([\d.,]+)\s*([KM]?)/;
  const MULT = { K: 1e3, M: 1e6, "": 1 };
  const COL = "Wishlist change";
  // тиры по числу вишлистов, набранных за фестиваль (бенчмарк How To Market A Game):
  // Diamond 10 000+, Gold 7 000–9 999, Silver 1 000–6 999, Bronze 0–999
  const TIERS = [
    { key: "diamond", medal: "\u{1F48E}", from: 10_000, to: null },
    { key: "gold", medal: "\u{1F947}", from: 7_000, to: 9_999 },
    { key: "silver", medal: "\u{1F948}", from: 1_000, to: 6_999 },
    { key: "bronze", medal: "\u{1F949}", from: null, to: 999 },
  ];
  const tierOf = (gain) =>
    TIERS.find((t) => gain >= (t.from ?? -Infinity) && gain <= (t.to ?? Infinity)) || TIERS[3];
  // режимы сортировки: 0 — исходный порядок, 1/2 — абсолютный прирост ↓/↑,
  // 3 — рост в разах ↓, 4 — прыжок в топе (▲) ↓
  const MODES = ["", "↓", "↑", "×↓", "▲↓"];
  const STATE = { mode: 0 };

  const toInt = (text) => {
    const n = parseInt(String(text ?? "").replace(/[^\d]/g, ""), 10);
    return Number.isFinite(n) ? n : null;
  };

  const fmtShort = (value) => {
    const abs = Math.abs(value);
    const sign = value < 0 ? "−" : "+";
    if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}${Math.round(abs / 1e3)}K`;
    return `${sign}${abs}`;
  };

  const fmtFull = (value) => value.toLocaleString("ru-RU");

  function parseWishlists(cell) {
    const m = WL_RE.exec(cell?.textContent || "");
    if (!m) return null;
    const arrow = m[2];
    // запятая — разделитель тысяч: 9,503 и 53,800 надо читать как 9503 и 53800
    const raw = parseFloat(String(m[4]).replace(/,/g, ""));
    if (!Number.isFinite(raw)) return null;
    return {
      rank: toInt(m[1]),
      jump: arrow ? (toInt(m[3]) || 0) * (arrow === "\u25b2" ? 1 : -1) : 0,
      est: Math.round(raw * MULT[m[5] || ""]),
    };
  }

  function mainTable() {
    const tables = Array.from(document.querySelectorAll("table"));
    return tables.sort(
      (a, b) => b.querySelectorAll("tbody tr").length - a.querySelectorAll("tbody tr").length
    )[0];
  }

  /** Кривая «место в топе → вишлисты» по самой таблице (лог-лог, кусочно-линейно). */
  function buildCurve(rows) {
    const pts = rows
      .map((r) => r.wl)
      .filter((w) => w && w.rank && w.est)
      .map((w) => [w.rank, w.est])
      .sort((a, b) => a[0] - b[0]);
    if (pts.length < 2) return () => null;
    return (rank) => {
      if (rank <= pts[0][0]) return pts[0][1];
      if (rank >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
      let lo = 0;
      let hi = pts.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (pts[mid][0] <= rank) lo = mid;
        else hi = mid;
      }
      const [x0, y0] = pts[lo];
      const [x1, y1] = pts[hi];
      const t = x1 === x0 ? 0 : (rank - x0) / (x1 - x0);
      return Math.exp(Math.log(y0) + t * (Math.log(y1) - Math.log(y0)));
    };
  }

  function readRows(table) {
    return Array.from(table.querySelectorAll("tbody tr")).map((tr) => {
      // свою колонку исключаем: иначе при повторном прогоне последней ячейкой
      // окажется она сама и данные строки потеряются
      const cells = Array.from(tr.querySelectorAll("td,th")).filter(
        (c) => !c.classList.contains("pr-gain")
      );
      return { tr, cells, wl: cells.length ? parseWishlists(cells[cells.length - 1]) : null };
    });
  }

  function headerRow(table) {
    return table.querySelector("thead tr") || table.querySelector("tbody tr");
  }

  function sortRows(table, rows) {
    const body = table.querySelector("tbody");
    if (!body) return;
    const list = rows.slice();

    if (STATE.mode === 0) {
      list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    } else {
      // «нет данных» — это не «мало», поэтому такие строки всегда в конце,
      // независимо от направления сортировки
      const value = (row) => {
        if (STATE.mode === 1 || STATE.mode === 2) return Number.isFinite(row.gain) ? row.gain : null;
        if (STATE.mode === 3) return Number.isFinite(row.ratio) ? row.ratio : null;
        return Number.isFinite(row.jump) ? row.jump : null;
      };
      const asc = STATE.mode === 2;
      list.sort((a, b) => {
        const av = value(a);
        const bv = value(b);
        if (av === null && bv === null) return (a.order ?? 0) - (b.order ?? 0);
        if (av === null) return 1;
        if (bv === null) return -1;
        return asc ? av - bv : bv - av;
      });
    }
    for (const row of list) body.appendChild(row.tr);
  }

  function collectForSort(table) {
    return readRows(table).map((r) => {
      const cell = r.tr.querySelector("td.pr-gain");
      const gain = cell && cell.dataset.gain ? Number(cell.dataset.gain) : NaN;
      const ratio = cell && cell.dataset.ratio ? Number(cell.dataset.ratio) : NaN;
      const jump = cell && cell.dataset.jump ? Number(cell.dataset.jump) : NaN;
      return {
        tr: r.tr,
        gain,
        ratio,
        jump,
        order: Number(r.tr.dataset.prOrder || 0),
      };
    });
  }

  function decorate() {
    const table = mainTable();
    if (!table) return false;

    const rows = readRows(table);
    if (!rows.length || !rows.some((r) => r.wl)) return false;
    const at = buildCurve(rows);

    rows.forEach((row, index) => {
      if (row.tr.dataset.prOrder === undefined) row.tr.dataset.prOrder = String(index);
      if (row.wl && row.wl.jump && row.wl.rank) {
        const rankBefore = row.wl.rank + row.wl.jump;
        const before = at(rankBefore);
        row.gain = before == null ? null : Math.round(row.wl.est - before);
        row.rankBefore = rankBefore;
        row.estBefore = before == null ? null : Math.round(before);
      } else {
        row.gain = null;
      }
    });

    const head = headerRow(table);
    if (head && !head.querySelector("th[data-pr-gain]")) {
      const th = document.createElement("th");
      th.dataset.prGain = "1";
      th.title =
        "Оценка вишлистов, набранных за фестиваль. Медали — тиры How To Market A Game: " +
        "💎 10 000+, 🥇 7 000–9 999, 🥈 1 000–6 999, 🥉 0–999. " +
        "Клик переключает сортировку: по приросту ↓ → ↑ → рост в разах → прыжок в топе → исходный порядок.";
      th.innerHTML = `${COL}<span class="pr-sort"></span>`;
      th.addEventListener("click", () => {
        STATE.mode = (STATE.mode + 1) % MODES.length;
        th.querySelector(".pr-sort").textContent = MODES[STATE.mode];
        sortRows(table, collectForSort(table));
      });
      head.appendChild(th);
    }

    let added = 0;
    for (const row of rows) {
      if (row.tr.querySelector("td.pr-gain")) continue;
      const td = document.createElement("td");
      td.className = "pr-gain";
      if (row.gain == null) {
        td.classList.add("pr-none");
        td.textContent = "—";
        td.title = row.wl ? "Прыжка в топе нет — считать нечего" : "Нет данных о вишлистах";
      } else {
        const tier = tierOf(row.gain);
        td.textContent = `${tier.medal} ${fmtShort(row.gain)}`;
        td.classList.add(row.gain >= 0 ? "pr-pos" : "pr-neg");
        td.dataset.gain = String(row.gain);
        td.dataset.tier = tier.key;
        td.dataset.jump = String(row.wl.jump);
        const ratio = row.estBefore ? row.wl.est / row.estBefore : null;
        if (ratio) td.dataset.ratio = String(ratio);
        td.title =
          `${tier.medal} ${tier.key} (${tier.from === null ? `0–${tier.to.toLocaleString("ru-RU")}`
            : tier.to === null ? `${tier.from.toLocaleString("ru-RU")}+`
            : `${tier.from.toLocaleString("ru-RU")}–${tier.to.toLocaleString("ru-RU")}`} вишлистов за фестиваль)\n` +
          `#${row.wl.rank}▲${row.wl.jump} ≈${fmtFull(row.wl.est)} вишлистов сейчас\n` +
          `было на #${row.rankBefore}: ≈${fmtFull(row.estBefore)}\n` +
          `оценка прироста: ${fmtFull(row.gain)} (±20–30%)` +
          (ratio ? `\nрост: ×${ratio.toFixed(2)} за фестиваль` : "");
      }
      row.tr.appendChild(td);
      added += 1;
    }
    return added > 0;
  }

  // страница дорисовывает таблицу и перерисовывает её при обновлении — следим за DOM
  let timer = null;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      try {
        decorate();
      } catch (err) {
        console.warn("[playrecon-gain]", err);
      }
    }, 400);
  };

  const start = () => {
    if (decorate()) console.info("[playrecon-gain] колонка добавлена");
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    schedule();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

