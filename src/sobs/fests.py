"""Календарь изданий Steam Next Fest.

ВАЖНО о точности:
* `start`/`end` — ориентировочные окна (нужны только для поиска архивных
  снапшотов). Авторитетная принадлежность снапшота к изданию определяется
  по заголовку архивной страницы (`Steam Next Fest | October 2021`).
* `expected` — контрольные числа участников по данным GameDiscoverCo
  (июнь 2023 — июнь 2026) и How To Market A Game (октябрь 2026, статья
  "How sloppy is the October 2026 Steam Next Fest", 21.10.2026).
  Используются как проверка качества бэкфилла: если распарсили ~столько же
  игр, значит извлекли полный список.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fest:
    slug: str  # машинный идентификатор, напр. "oct2026"
    label_en: str
    label_ru: str
    season: str  # winter | spring | summer | autumn
    start: str  # YYYY-MM-DD (ориентировочно)
    end: str  # YYYY-MM-DD (ориентировочно)
    expected: int | None = None  # контрольное число участников

    @property
    def year(self) -> int:
        return int(self.start[:4])


FESTS: list[Fest] = [
    Fest("jun2021", "June 2021", "Июнь 2021", "summer", "2021-06-16", "2021-06-22"),
    Fest("oct2021", "October 2021", "Октябрь 2021", "autumn", "2021-10-01", "2021-10-07"),
    Fest("feb2022", "February 2022", "Февраль 2022", "winter", "2022-02-21", "2022-02-28"),
    Fest("jun2022", "June 2022", "Июнь 2022", "summer", "2022-06-13", "2022-06-20"),
    Fest("oct2022", "October 2022", "Октябрь 2022", "autumn", "2022-10-03", "2022-10-10"),
    Fest("feb2023", "February 2023", "Февраль 2023", "winter", "2023-02-06", "2023-02-13"),
    Fest("jun2023", "June 2023", "Июнь 2023", "summer", "2023-06-19", "2023-06-26", 887),
    Fest("oct2023", "October 2023", "Октябрь 2023", "autumn", "2023-10-09", "2023-10-16", 972),
    Fest("feb2024", "February 2024", "Февраль 2024", "winter", "2024-02-05", "2024-02-12", 1123),
    Fest("jun2024", "June 2024", "Июнь 2024", "summer", "2024-06-10", "2024-06-17", 1805),
    Fest("oct2024", "October 2024", "Октябрь 2024", "autumn", "2024-10-14", "2024-10-21", 3008),
    Fest("feb2025", "February 2025", "Февраль 2025", "winter", "2025-02-24", "2025-03-03", 2337),
    Fest("jun2025", "June 2025", "Июнь 2025", "summer", "2025-06-09", "2025-06-16", 2645),
    Fest("oct2025", "October 2025", "Октябрь 2025", "autumn", "2025-10-13", "2025-10-20", 2963),
    Fest("feb2026", "February 2026", "Февраль 2026", "winter", "2026-02-23", "2026-03-02", 3536),
    Fest("jun2026", "June 2026", "Июнь 2026", "summer", "2026-06-15", "2026-06-22", 4382),
    Fest("oct2026", "October 2026", "Октябрь 2026", "autumn", "2026-10-19", "2026-10-26", 7240),
]


def by_slug(slug: str) -> Fest:
    for fest in FESTS:
        if fest.slug == slug:
            return fest
    raise KeyError(slug)
