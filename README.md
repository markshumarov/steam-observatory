# Steam Observatory

Открытый пайплайн данных об игровой индустрии: **Steam как основной источник**,
интерактивные графики вместо статей и честная методология.

Open data pipeline about the games industry, with **Steam as the primary source**:
interactive charts first, articles second, and a transparent methodology.

## Что это / What it is

Дата-журналистика об играх в духе Silver Bulletin: числа и интерактив первичны,
текст и стримы — вторичны. Первый большой сюжет — **Steam Next Fest**: состав
участников, насыщенность тегов, концентрация вишлистов, что происходило с играми
после фестиваля.

Data journalism about games, Silver Bulletin style: numbers and interactivity first.
The first big story is **Steam Next Fest**: lineups, tag saturation, wishlist
concentration, and what happened to those games afterwards.

## Статус / Status

Ранняя стадия. Собраны и проверены источники данных (см. `docs/data-sources.md`),
работает бэкфилл составов фестивалей из Wayback Machine.

Early stage. Data sources verified (see `docs/data-sources.md`); the Wayback
backfill of Next Fest lineups works.

## Структура / Layout

```
src/sobs/            # библиотека сбора данных
  config.py          # пути, лимиты, UA
  http.py            # HTTP с ретраями, вежливым rate limit и кэшем на диске
  fests.py           # календарь изданий Steam Next Fest
  parse.py           # разбор страниц Steam -> структурированные записи
  sources/wayback.py # Wayback Machine (CDX API + загрузка снапшотов)
scripts/             # запускаемые скрипты (бэкфилл, разведка)
data/raw/            # сырые дампы (в git не попадают)
data/processed/      # нормализованные данные (JSON/parquet)
docs/                # методология и источники
```

## Быстрый старт / Quick start

```bash
pip install -r requirements.txt

# бэкфилл составов всех изданий Next Fest из Wayback Machine
python scripts/backfill_nextfest.py

# одно издание
python scripts/backfill_nextfest.py --only oct2026
```

## Данные / Data

| Слой | Что | Источник |
|---|---|---|
| A | состав фестивалей, теги, даты релиза | Wayback Machine (архивы `store.steampowered.com/sale/nextfest`) |
| B | игроки в демо (CCU), динамика фестиваля | Steam public API, внешние открытые API |
| C | исходы после релиза (отзывы, игроки) | Steam public API, внешние открытые API |

Вишлисты Steam не публикует: любые числа вишлистов в проекте — **оценки** и всегда
помечаются как оценки. Подробности: `docs/methodology.md`.

## План / Roadmap

| Этап | Что | Статус |
|---|---|---|
| M0 | Разведка источников, проверка эндпоинтов | **готово** (`docs/data-sources.md`) |
| M0 | Состав текущего фестиваля (октябрь 2026) | **готово**: 7 304 игры + гистограмма по 421 тегу |
| M0 | Мэппинг «игра → демо» и опрос CCU демо | **в работе** (`ingest_demo_map.py`, `poll_ccu.py`) |
| M1 | Бэкфилл составов 2021–2022 из Wayback (с тегами) | **готово**: июнь 2021 — 609 игр с тегами |
| M1 | Бэкфилл 2023+ через архивированные XHR | скрипт готов (`backfill_lineup_ajax.py`) |
| M1 | Обогащение метаданными (цена, даты релиза, платформы) | не начато |
| M2 | Сайт: интерактивные вью по фестам (Astro + DuckDB-WASM + Observable Plot) | не начато |
| M3 | Модель «вишлисты/CCU → результат» + what-if калькулятор | не начато |
| M4 | Статьи, подкаст, открытый датасет для цитирования | не начато |

### Ближайшие шаги

1. Дождаться мэппинга демо и снять CCU-профиль последнего дня фестиваля.
2. Восстановить составы 2023–2026 из архивированных XHR (`--fetch`).
3. Свести всё в parquet + `data/processed/nextfest/*.json` и опубликовать первый
   интерактивный отчёт: насыщенность по тегам, концентрация, доля AI-игр.
4. Перенести сбор в GitHub Actions (cron), чтобы данные обновлялись без локальных запусков.

## Лицензии / Licenses

* код — MIT (`LICENSE`);
* производные данные — CC BY 4.0 (`DATA-LICENSE.md`).

Steam и связанные материалы принадлежат Valve Corporation. Проект не аффилирован
с Valve. Все внешние источники перечислены в `docs/data-sources.md`.
