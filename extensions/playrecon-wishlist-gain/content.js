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
  // у топовых игр PlayRecon показывает только место и прыжок (#34▲12), без ≈N:
  // такие строки тоже нужны — число вишлистов для них берём из Gamalytic
  const WL_RE_RANK = /#([\d\s,]+)(?:([\u25b2\u25bc])\s*([\d\s,]+))?/;
  const MULT = { K: 1e3, M: 1e6, "": 1 };
  const COL = "Wishlist change";
  // вторая колонка: тот же прирост, но в процентах от текущего числа вишлистов
  // (медиана по фестивалю — 12%, p90 — 29%)
  const PCT_COL = "Change %";
  const PCT_MODES = ["", "↓", "↑"];
  // третья колонка: текущее число вишлистов из Gamalytic (внешний источник,
  // независимый от модели PlayRecon) — для сверки оценок
  const GCOL = "Wishlists (Gamalytic)";
  const GAL_MODES = ["", "↓", "↑"];
  const HAS_WORKER = typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.id;
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
  const STATE = { mode: 0, modePct: 0, modeGal: 0 };
  // строки последнего прогона: нужны, чтобы пересчитать кривую, когда придут
  // данные Gamalytic (они асинхронные и приходят уже после первой отрисовки)
  let lastRows = [];
  let refreshTimer = null;
  const scheduleRefresh = () => {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshGainCells, 900);
  };

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
    const text = cell?.textContent || "";
    const m = WL_RE.exec(text);
    if (!m) {
      const loose = WL_RE_RANK.exec(text);
      if (!loose) return null;
      const arrow = loose[2];
      return {
        rank: toInt(loose[1]),
        jump: arrow ? (toInt(loose[3]) || 0) * (arrow === "\u25b2" ? 1 : -1) : 0,
        est: null, // оценки нет: подставим данные Gamalytic
      };
    }
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

  /** Кривая «место в топе → вишлисты» по самой таблице (лог-лог, кусочно-линейно).
      Строится только на числах PlayRecon: она задаёт ФОРМУ (во сколько раз на месте
      до фестиваля было меньше), а уровень берём из Gamalytic отдельно. Смешивать
      две модели в одной кривой нельзя — шкалы разные. */
  function buildCurve(rows, pick = (r) => r.wl && r.wl.est) {
    const pts = rows
      .map((r) => (r.wl && r.wl.rank ? [r.wl.rank, pick(r)] : null))
      .filter((p) => p && p[1])
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
      // appid игры берём из картинки строки: .../apps/5133900/...
      const img = tr.querySelector("img");
      const m = img && /\/apps\/(\d+)\//.exec(img.src || "");
      const appid = m ? Number(m[1]) : null;
      // свои колонки исключаем: иначе при повторном прогоне последней ячейкой
      // окажется она сама и данные строки потеряются
      const cells = Array.from(tr.querySelectorAll("td,th")).filter(
        (c) => !["pr-gain", "pr-pct", "pr-gal"].some((x) => c.classList.contains(x))
      );
      return { tr, cells, appid, wl: cells.length ? parseWishlists(cells[cells.length - 1]) : null };
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

  function sortByPct(table, rows) {
    const body = table.querySelector("tbody");
    if (!body) return;
    const list = rows.slice();
    if (STATE.modePct === 0) {
      list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    } else {
      const value = (row) => {
        const cell = row.tr.querySelector("td.pr-pct");
        return cell && cell.dataset.pct ? Number(cell.dataset.pct) : null;
      };
      const asc = STATE.modePct === 2;
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

  const fmtCompact = (value) =>
    value >= 1e6 ? `${(value / 1e6).toFixed(1)}M` : value >= 1e3 ? `${Math.round(value / 1e3)}K` : String(value);

  function sortByGal(table, rows) {
    const body = table.querySelector("tbody");
    if (!body) return;
    const list = rows.slice();
    if (STATE.modeGal === 0) {
      list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    } else {
      const value = (row) => {
        const cell = row.tr.querySelector("td.pr-gal");
        return cell && cell.dataset.gal ? Number(cell.dataset.gal) : null;
      };
      const asc = STATE.modeGal === 2;
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
    lastRows = rows;
    const at = buildCurve(rows);

    rows.forEach((row, index) => {
      if (row.tr.dataset.prOrder === undefined) row.tr.dataset.prOrder = String(index);
      if (row.wl && row.wl.jump && row.wl.rank) {
        const rankBefore = row.wl.rank + row.wl.jump;
        // «сейчас» и «до» по шкале PlayRecon: если у игры своей оценки нет
        // (топ выше калибровки модели), берём значение кривой на её месте
        const nowPr = row.wl.est ?? at(row.wl.rank);
        const beforePr = at(rankBefore);
        if (nowPr && beforePr) {
          const ratio = beforePr / nowPr; // во сколько раз «до» меньше «сейчас»
          // уровень — Gamalytic, если он ответил, иначе шкала PlayRecon
          const level = row.gal ?? nowPr;
          row.nowValue = level;
          row.estBefore = Math.round(level * ratio);
          row.gain = Math.round(level * (1 - ratio));
          row.pct = Math.round(1000 * (1 - ratio)) / 10;
          row.rankBefore = rankBefore;
        } else {
          row.gain = null;
          row.pct = null;
        }
      } else {
        row.gain = null;
        row.pct = null;
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

    if (head && !head.querySelector("th[data-pr-pct]")) {
      const th = document.createElement("th");
      th.dataset.prPct = "1";
      th.title =
        "Прирост вишлистов за фестиваль в процентах от текущего числа: " +
        "сколько из нынешнего списка набрано за неделю фестиваля. Медиана по фестивалю — 12%, " +
        "p90 — 29%. Клик переключает сортировку: по убыванию → по возрастанию → исходный порядок.";
      th.innerHTML = `${PCT_COL}<span class="pr-sort"></span>`;
      th.addEventListener("click", () => {
        STATE.modePct = (STATE.modePct + 1) % PCT_MODES.length;
        th.querySelector(".pr-sort").textContent = PCT_MODES[STATE.modePct];
        sortByPct(table, readRows(table));
      });
      head.appendChild(th);
    }

    if (HAS_WORKER && head && !head.querySelector("th[data-pr-gal]")) {
      const th = document.createElement("th");
      th.dataset.prGal = "1";
      th.title =
        "Текущее число вишлистов по оценке Gamalytic — независимый источник, с которым " +
        "можно сверить нашу оценку из рангов PlayRecon. Клик переключает сортировку: " +
        "по убыванию → по возрастанию → исходный порядок.";
      th.innerHTML = `${GCOL}<span class="pr-sort"></span>`;
      th.addEventListener("click", () => {
        STATE.modeGal = (STATE.modeGal + 1) % GAL_MODES.length;
        th.querySelector(".pr-sort").textContent = GAL_MODES[STATE.modeGal];
        sortByGal(table, readRows(table));
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
        const now = row.nowValue ?? row.gal ?? row.wl.est;
        const ratio = row.estBefore && now ? now / row.estBefore : null;
        if (ratio) td.dataset.ratio = String(ratio);
        td.title =
          `${tier.medal} ${tier.key} (${tier.from === null ? `0–${tier.to.toLocaleString("ru-RU")}`
            : tier.to === null ? `${tier.from.toLocaleString("ru-RU")}+`
            : `${tier.from.toLocaleString("ru-RU")}–${tier.to.toLocaleString("ru-RU")}`} вишлистов за фестиваль)\n` +
          `#${row.wl.rank}▲${row.wl.jump} ` +
          (now
            ? `≈${fmtFull(now)} вишлистов сейчас (${row.gal ? "Gamalytic" : "PlayRecon"})`
            : "вишлисты сейчас: нет данных") + "\n" +
          (row.estBefore ? `было на #${row.rankBefore}: ≈${fmtFull(row.estBefore)}\n` : "") +
          `оценка прироста: ${fmtFull(row.gain)} (±20–30%)` +
          (ratio ? `\nрост: ×${ratio.toFixed(2)} за фестиваль` : "");
      }
      row.tr.appendChild(td);
      added += 1;
    }

    // вторая колонка: тот же прирост в процентах от текущего числа вишлистов
    for (const row of rows) {
      if (row.tr.querySelector("td.pr-pct")) continue;
      const td = document.createElement("td");
      td.className = "pr-pct";
      if (row.pct == null) {
        td.classList.add("pr-none");
        td.textContent = "—";
        td.title = row.wl ? "Прыжка в топе нет — считать нечего" : "Нет данных о вишлистах";
      } else {
        td.textContent = `${row.pct.toFixed(1)}%`;
        td.dataset.pct = String(row.pct);
        td.classList.add(row.pct >= 0 ? "pr-pos" : "pr-neg");
        td.title =
          `За фестиваль набрано ${row.pct.toFixed(1)}% текущего числа вишлистов\n` +
          `прирост ≈${fmtFull(row.gain)} из ≈${fmtFull(row.nowValue ?? row.gal ?? row.wl.est ?? 0)} (±20–30%)\n` +
          `медиана по фестивалю — 12%, p90 — 29%`;
      }
      row.tr.appendChild(td);
      added += 1;
    }
    // третья колонка: вишлисты Gamalytic — приходят асинхронно из воркера
    if (HAS_WORKER) {
      for (const row of rows) {
        if (row.tr.querySelector("td.pr-gal") || !row.appid) continue;
        const td = document.createElement("td");
        td.className = "pr-gal pr-none";
        td.textContent = "…";
        td.title = "Запрашиваем текущее число вишлистов у Gamalytic";
        row.tr.appendChild(td);
        added += 1;
        const ours = row.wl && row.wl.est ? row.wl.est : null;
        chrome.runtime.sendMessage(
          { type: "gamalytic-wishlists", appid: row.appid },
          (res) => {
            if (!res || !res.wishlists) {
              td.textContent = "—";
              td.title = "Gamalytic не отдал число вишлистов для этой игры";
              return;
            }
            td.classList.remove("pr-none");
            td.textContent = fmtCompact(res.wishlists);
            td.dataset.gal = String(res.wishlists);
            row.gal = res.wishlists;
            // пересчитываем наши две колонки на данных Gamalytic
            scheduleRefresh();
            const diff = ours ? 100 * (res.wishlists / ours - 1) : null;
            td.title =
              `Gamalytic: ≈${fmtFull(res.wishlists)} вишлистов сейчас` +
              (res.topWish ? `\nместо в топе вишлистов: #${fmtFull(res.topWish)}` : "") +
              (diff == null
                ? "\nнаша оценка PlayRecon для этой игры недоступна"
                : `\nнаш PlayRecon: ≈${fmtFull(ours)} — расхождение ` +
                  `${diff > 0 ? "+" : ""}${diff.toFixed(1)}%`);
          }
        );
      }
    }

    return added > 0;
  }

  /** Пересчёт наших двух колонок на данных Gamalytic: убираем ячейки, decorate()
      строит их заново — уже по кривой, где «сейчас» берётся из Gamalytic. */
  function refreshGainCells() {
    if (!lastRows.length) return;
    try {
      for (const row of lastRows) {
        const gain = row.tr.querySelector("td.pr-gain");
        const pct = row.tr.querySelector("td.pr-pct");
        if (gain) gain.remove();
        if (pct) pct.remove();
      }
      decorate();
    } catch (err) {
      console.warn("[playrecon-gain] пересчёт не удался", err);
    }
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

