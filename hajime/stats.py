"""Pure helpers for the study-activity heatmap (no GUI)."""

from __future__ import annotations

from datetime import date, timedelta

# Upper bounds (exclusive, in seconds) for heat levels 1..3; anything above is level 4.
LEVEL_LIMITS = (30 * 60, 60 * 60, 2 * 3600)


def level(seconds: int) -> int:
    """Heat level 0 (nothing) to 4 (a lot) for a day's studied seconds."""
    if seconds <= 0:
        return 0
    for lvl, limit in enumerate(LEVEL_LIMITS, start=1):
        if seconds < limit:
            return lvl
    return len(LEVEL_LIMITS) + 1


def fmt_duration(seconds: int) -> str:
    hours, rest = divmod(max(0, int(seconds)), 3600)
    minutes = rest // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def seconds_on(history: dict[str, int], day: date) -> int:
    return history.get(day.isoformat(), 0)


def year_weeks(year: int) -> list[list[date | None]]:
    """Monday-first week columns covering ``year``; days outside it are ``None``."""
    first, last = date(year, 1, 1), date(year, 12, 31)
    cursor = first - timedelta(days=first.weekday())
    weeks = []
    while cursor <= last:
        weeks.append([d if first <= d <= last else None
                      for d in (cursor + timedelta(days=i) for i in range(7))])
        cursor += timedelta(days=7)
    return weeks


def year_total(history: dict[str, int], year: int) -> int:
    prefix = f"{year:04d}-"
    return sum(s for d, s in history.items() if d.startswith(prefix))


def month_totals(history: dict[str, int], year: int) -> list[int]:
    totals = [0] * 12
    for iso, seconds in history.items():
        try:
            day = date.fromisoformat(iso)
        except ValueError:
            continue
        if day.year == year:
            totals[day.month - 1] += seconds
    return totals


def active_days(history: dict[str, int], year: int) -> int:
    prefix = f"{year:04d}-"
    return sum(1 for d, s in history.items() if d.startswith(prefix) and s > 0)


def streaks(history: dict[str, int], today: date | None = None) -> tuple[int, int]:
    """Return ``(current, longest)`` runs of consecutive studied days.

    The current streak stays alive through today if nothing was studied yet.
    """
    today = today or date.today()
    days = set()
    for iso, seconds in history.items():
        if seconds > 0:
            try:
                days.add(date.fromisoformat(iso))
            except ValueError:
                continue
    longest = run = 0
    previous = None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    cursor = today if today in days else today - timedelta(days=1)
    current = 0
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def years_available(history: dict[str, int], today: date | None = None) -> tuple[int, int]:
    """Inclusive ``(first_year, last_year)`` that the year picker may show."""
    today = today or date.today()
    years = [today.year]
    for iso in history:
        try:
            years.append(date.fromisoformat(iso).year)
        except ValueError:
            continue
    return min(years), max(years)
