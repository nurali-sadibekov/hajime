from datetime import date

from hajime import stats


def test_level_thresholds():
    assert [stats.level(s) for s in (0, 1, 1800, 3600, 7200)] == [0, 1, 2, 3, 4]


def test_fmt_duration():
    assert stats.fmt_duration(59) == "0m"
    assert stats.fmt_duration(3600 + 120) == "1h 2m"


def test_year_weeks_cover_year_monday_first():
    weeks = stats.year_weeks(2026)
    days = [d for w in weeks for d in w if d]
    assert len(days) == 365 and days[0] == date(2026, 1, 1)
    assert all(len(w) == 7 for w in weeks)
    assert weeks[0][date(2026, 1, 1).weekday()] == date(2026, 1, 1)


def test_totals():
    history = {"2025-12-31": 100, "2026-01-02": 60, "2026-03-01": 40}
    assert stats.year_total(history, 2026) == 100
    assert stats.month_totals(history, 2026)[:3] == [60, 0, 40]
    assert stats.active_days(history, 2026) == 2


def test_streaks():
    h = {"2026-05-01": 1, "2026-05-02": 1, "2026-05-03": 1, "2026-05-10": 1, "2026-05-11": 1}
    assert stats.streaks(h, date(2026, 5, 11)) == (2, 3)
    assert stats.streaks(h, date(2026, 5, 12)) == (2, 3)  # today not studied yet
    assert stats.streaks(h, date(2026, 5, 14)) == (0, 3)


def test_years_available():
    assert stats.years_available({"2023-01-01": 5}, date(2026, 1, 1)) == (2023, 2026)
