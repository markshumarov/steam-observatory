// Тексты страницы-разбора. Числа подставляются из data/story.json.
export const S = {
  en: {
    h1: "Next Fest grew 12× in five years. Attention did not.",
    lede:
      "What the October 2026 lineup, the demo board and wishlist conversion say about shipping a demo today. Everything is dated 26 October 2026 and lists its source.",
    nav_tiers: "Tiers",
    nav_supply: "Supply",
    nav_attention: "Attention",
    nav_wishlists: "Wishlists",
    nav_cozy: "Cozy",
    nav_takeaways: "Takeaways",
    nav_data: "All data",

    tiers_title: "Every fifth demo earns 10,000+ wishlists",
    tiers_hint:
      "How many wishlists each demo earned during the festival, split into the tiers used by How To Market A Game (💎 10,000+, 🥇 7,000–9,999, 🥈 1,000–6,999, 🥉 0–999). Source: PlayRecon festival board, {total} games with a recorded wishlist-chart jump. The board is the top 1,000 demos by players, so successful games are over-represented here.",
    tiers_kicker: "{share}%",
    tiers_b1: "<b>{diamond}</b> demos earned 10,000+ wishlists (💎 Diamond) — {diamond_share}% of those we could measure.",
    tiers_b2: "The middle is crowded: <b>{silver}</b> demos ({silver_share}%) landed in Silver with 1,000–6,999 wishlists.",
    tiers_b3: "<b>{bronze}</b> demos ({bronze_share}%) stayed under 1,000 — including <b>{negatives}</b> whose wishlist estimate fell during the festival.",
    tiers_b4: "More Diamonds than Golds looks like a bug, but it is arithmetic: Gold is a 3,000-wide band while Diamond runs unbounded upward, and the count decays smoothly across the 10,000 line ({edge_below} demos landed in 9,000–9,999, {edge_above} in 10,000–10,999). An independent developer survey by How To Market A Game (February 2026, n≈170) implies the same ~2:1 ratio, and no demo here earned more than its current wishlist total — the median festival gain is {share_median}% of a demo's total.",
    tiers_axis: "demos",
    tiers_legend: "wishlists earned during the festival",

    supply_title: "The lineup is twelve times bigger than in 2021",
    supply_hint:
      "Participants per edition: archived festival pages for 2021–2024, the live endpoint for October 2026. Amber bars are partial reconstructions — the archived page only served part of the list.",
    supply_kicker: "{n}×",
    supply_games: "games",
    supply_b1: "<b>611 → {now}</b> participants in five years: the festival grew faster than the audience for demos.",
    supply_b2: "Every edition since October 2024 has more than <b>2,600</b> demos; October 2026 has <b>{now}</b>.",
    supply_b3: "A demo is no longer a rare event. It is the default.",

    attention_title: "Ten demos take two thirds of the attention",
    attention_hint:
      "Left: share of demo players inside the top-200 board. Right: peak concurrent players per demo across the entire October 2026 lineup (our polling, {samples} samples).",
    attention_kicker: "{share}%",
    attention_b1: "The top ten demos collect <b>{share}%</b> of all demo players in the top-200 board.",
    attention_b2: "Median demo in the full lineup: <b>{median}</b> concurrent players. <b>{dead}</b> of {games} demos never showed a single one.",
    attention_b3: "Only <b>{over100}</b> demos out of {games} ever crossed 100 concurrent players.",
    chart_board: "share of demo players, top-200 board",
    chart_peaks: "demos by peak players",
    top10: "top 10",
    next40: "11–50",
    rest: "51–200",
    demos: "demos",

    wishlists_title: "1,000 wishlists become about 6 reviews",
    wishlists_hint:
      "Reviews in the first {age} days per 1,000 wishlists estimated a week before release. {n} games released in 2026, quantiles (PlayRecon conversion benchmark).",
    wishlists_kicker: "6.1",
    wishlists_b1: "Median: <b>{p50}</b> reviews per 1,000 wishlists. The spread is brutal: p10 <b>{p10}</b>, p90 <b>{p90}</b> — a {spread}× difference.",
    wishlists_b2: "Games with <b>more</b> wishlists convert <b>worse</b>: {high} vs {low} reviews per 1,000. Large lists dilute.",
    wishlists_b3: "Median wishlist count in the cohort: <b>{wl}</b>. Wishlists are reach, not revenue.",
    q_p10: "p10",
    q_p25: "p25",
    q_p50: "median",
    q_p75: "p75",
    q_p90: "p90",
    per_1k: "reviews per 1,000 wishlists",

    cozy_title: "Cozy: 72× more releases, 39× fewer reviews",
    cozy_hint:
      "Index, 2019 = 100: how many games shipped with the tag, and their median review count. Cozy is the clearest case of a tag that stopped being a niche.",
    cozy_kicker: "{grown}×",
    cozy_b1: "Releases: <b>{first_rel}</b> in 2019 → <b>{last_rel}</b> in {last_year}. {last_12m} of them shipped in the last 12 months.",
    cozy_b2: "Median reviews: <b>{first_rev}</b> → <b>{last_rev}</b>. The audience did not grow {grown}×.",
    cozy_b3: "<b>{share}</b> of 2026 Cozy releases have fewer than 10 reviews — and {too_fresh} are still too fresh to judge.",
    cozy_releases: "releases (index)",
    cozy_reviews: "median reviews (index)",
    year: "year",

    takeaways_title: "What it means if you ship a demo",
    takeaways_hint: "Five practical consequences, each backed by the numbers above.",
    t1: "A demo buys you <b>visibility inside a crowd of thousands</b>, not visibility. Plan distribution as if the festival does not exist.",
    t2: "Judge the festival by <b>conversion of the people who already know you</b>: the median demo gets 2 concurrent players, so the bar for «it worked» is your own wishlist baseline, not the leaderboard.",
    t3: "Before choosing a tag, check <b>how many games shipped there in the last 12 months</b> and the median review count. Cozy in 2026: 1,377 releases, 17 reviews.",
    t4: "Do not optimise for <b>wishlist count</b> alone: above a certain size, conversion per wishlist falls. What converts is a specific promise to a specific audience.",
    t5: "Timing: October 2024 → October 2026 lineup grew <b>2.3×</b> ({from} → {to}). The same demo is worth less each edition.",

    method_title: "Sources and caveats",
    method_p1:
      "Copies sold and review scores are Gamalytic estimates, not Valve data; sales accumulate over time, so editions are compared only where the age is stated. Wishlist numbers are PlayRecon estimates from their wishlist-rank model, which their API marks experimental.",
    method_p2:
      "PlayRecon also supplies the demo board and the niche statistics; we publish their numbers with attribution and keep the raw responses out of the repository. Our own figures — lineup sizes, tag shares, demo players — are collected by scripts in the repository and can be reproduced.",
    th_source: "Source",
    what: "What it provides",
    note: "Note",
    footer: "Steam Observatory · analysis for {year} · Steam is a trademark of Valve Corporation",
    loading: "loading…",
  },

  ru: {
    h1: "Next Fest вырос в 12 раз за пять лет. Внимание — нет.",
    lede:
      "Что состав октября 2026, таблица демо и конверсия вишлистов говорят о выпуске демо сегодня. Все данные на 26 октября 2026, у каждой цифры указан источник.",
    nav_tiers: "Тиры",
    nav_supply: "Предложение",
    nav_attention: "Внимание",
    nav_wishlists: "Вишлисты",
    nav_cozy: "Cozy",
    nav_takeaways: "Выводы",
    nav_data: "Все данные",

    tiers_title: "Каждое пятое демо набирает 10 000+ вишлистов",
    tiers_hint:
      "Сколько вишлистов каждая игра набрала за фестиваль — в тирах How To Market A Game (💎 10 000+, 🥇 7 000–9 999, 🥈 1 000–6 999, 🥉 0–999). Источник: таблица фестиваля PlayRecon, {total} игр с зафиксированным прыжком в топе вишлистов. Это топ-1000 демо по игрокам, поэтому успешные игры здесь представлены с избытком.",
    tiers_kicker: "{share}%",
    tiers_b1: "<b>{diamond}</b> демо набрали 10 000+ вишлистов (💎 Diamond) — {diamond_share}% от тех, где получилось измерить.",
    tiers_b2: "Середина переполнена: <b>{silver}</b> демо ({silver_share}%) попали в Silver — это 1 000–6 999 вишлистов.",
    tiers_b3: "<b>{bronze}</b> демо ({bronze_share}%) не добрали и 1 000 — включая <b>{negatives}</b>, у которых оценка вишлистов за фестиваль упала.",
    tiers_b4: "Бриллиантов больше, чем золота, — похоже на ошибку, но это арифметика: Gold — полоса шириной 3 000, а Diamond тянется без верхней границы, и число игр убывает плавно через отметку 10 000 ({edge_below} демо попало в 9 000–9 999, {edge_above} — в 10 000–10 999). Независимый опрос разработчиков How To Market A Game (февраль 2026, n≈170) даёт то же соотношение ~2:1, и ни одно демо здесь не набрало больше, чем у него вишлистов сейчас: медианный прирост за фестиваль — {share_median}% от общего числа.",
    tiers_axis: "демо",
    tiers_legend: "вишлистов набрано за фестиваль",

    supply_title: "Состав в двенадцать раз больше, чем в 2021-м",
    supply_hint:
      "Участники по изданиям: архивные страницы фестиваля за 2021–2024 и живой эндпоинт для октября 2026. Янтарные столбцы — частичная реконструкция: архивная страница отдавала только часть списка.",
    supply_kicker: "{n}×",
    supply_games: "игр",
    supply_b1: "<b>611 → {now}</b> участников за пять лет: фестиваль рос быстрее, чем аудитория демо.",
    supply_b2: "В каждом издании с октября 2024 больше <b>2 600</b> демо; в октябре 2026 — <b>{now}</b>.",
    supply_b3: "Демо перестало быть редким событием. Оно стало нормой по умолчанию.",

    attention_title: "Десять демо забирают две трети внимания",
    attention_hint:
      "Слева: доля игроков в топ-200 таблицы. Справа: пик одновременных игроков по каждому демо всего состава октября 2026 (наши замеры, {samples} наблюдений).",
    attention_kicker: "{share}%",
    attention_b1: "Топ-10 демо собирают <b>{share}%</b> всех игроков топ-200.",
    attention_b2: "Медианное демо по всему составу: <b>{median}</b> одновременных игрока. <b>{dead}</b> из {games} демо не показали ни одного.",
    attention_b3: "Только <b>{over100}</b> демо из {games} когда-либо перешагнули 100 одновременных игроков.",
    chart_board: "доля игроков, топ-200",
    chart_peaks: "демо по пику игроков",
    top10: "топ-10",
    next40: "11–50",
    rest: "51–200",
    demos: "демо",

    wishlists_title: "1 000 вишлистов превращаются примерно в 6 отзывов",
    wishlists_hint:
      "Отзывы за первые {age} дней на 1 000 вишлистов, оценённых за неделю до релиза. {n} игр, вышедших в 2026, квантили (бенчмарк конверсии PlayRecon).",
    wishlists_kicker: "6.1",
    wishlists_b1: "Медиана: <b>{p50}</b> отзыва на 1 000 вишлистов. Разброс жёсткий: p10 <b>{p10}</b>, p90 <b>{p90}</b> — разница в {spread} раза.",
    wishlists_b2: "У игр с <b>больше</b> вишлистов конверсия <b>хуже</b>: {high} против {low} отзывов на 1 000. Большие списки размываются.",
    wishlists_b3: "Медианное число вишлистов в когорте: <b>{wl}</b>. Вишлисты — это охват, а не выручка.",
    q_p10: "p10",
    q_p25: "p25",
    q_p50: "медиана",
    q_p75: "p75",
    q_p90: "p90",
    per_1k: "отзывов на 1 000 вишлистов",

    cozy_title: "Cozy: релизов в 72 раза больше, отзывов в 39 раз меньше",
    cozy_hint:
      "Индекс, 2019 = 100: сколько игр вышло с тегом и какова медиана их отзывов. Cozy — самый чистый пример тега, переставшего быть нишей.",
    cozy_kicker: "{grown}×",
    cozy_b1: "Релизы: <b>{first_rel}</b> в 2019 → <b>{last_rel}</b> в {last_year}. Из них {last_12m} вышли за последние 12 месяцев.",
    cozy_b2: "Медиана отзывов: <b>{first_rev}</b> → <b>{last_rev}</b>. Аудитория не выросла в {grown} раз.",
    cozy_b3: "<b>{share}</b> релизов Cozy 2026 имеют меньше 10 отзывов, а {too_fresh} ещё слишком свежие для оценки.",
    cozy_releases: "релизы (индекс)",
    cozy_reviews: "медиана отзывов (индекс)",
    year: "год",

    takeaways_title: "Что это значит, если вы выпускаете демо",
    takeaways_hint: "Пять практических следствий, каждое опирается на цифры выше.",
    t1: "Демо покупает <b>заметность внутри толпы из тысяч</b>, а не саму заметность. Планируйте дистрибуцию так, будто фестиваля нет.",
    t2: "Оценивайте фестиваль по <b>конверсии тех, кто уже вас знает</b>: медианное демо собирает 2 игрока, поэтому планка «сработало» — ваш собственный уровень вишлистов, а не лидерборд.",
    t3: "Перед выбором тега посмотрите, <b>сколько игр вышло в нём за 12 месяцев</b> и какая там медиана отзывов. Cozy в 2026: 1 377 релизов, 17 отзывов.",
    t4: "Не оптимизируйте <b>число вишлистов</b>: выше определённого размера конверсия на вишлист падает. Конвертирует конкретное обещание конкретной аудитории.",
    t5: "Тайминг: с октября 2024 по октябрь 2026 состав вырос в <b>2.3 раза</b> ({from} → {to}). Одно и то же демо стоит меньше с каждым изданием.",

    method_title: "Источники и оговорки",
    method_p1:
      "Тираж и доля положительных отзывов — оценки Gamalytic, а не данные Valve; тираж накапливается со временем, поэтому издания сравниваются только там, где указан возраст. Вишлисты — оценки PlayRecon по модели вишлист-рангов, которую их API помечает как экспериментальную.",
    method_p2:
      "PlayRecon также даёт таблицу демо и статистику ниш; их числа мы публикуем с атрибуцией, а сырые ответы в репозиторий не кладём. Наши собственные цифры — размеры составов, доли тегов, игроки в демо — собраны скриптами из репозитория и воспроизводимы.",
    th_source: "Источник",
    what: "Что даёт",
    note: "Примечание",
    footer: "Steam Observatory · разбор за {year} · Steam — торговая марка Valve Corporation",
  },
};
