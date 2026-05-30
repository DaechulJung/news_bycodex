from datetime import date
from pathlib import Path

from news_bycodex.report_dates import existing_report_dates, missing_report_dates


def test_missing_report_dates_covers_every_gap_from_earliest_existing_through_today():
    existing = {
        date(2026, 5, 3),
        date(2026, 5, 4),
        date(2026, 5, 6),
    }

    assert missing_report_dates(existing, date(2026, 5, 8)) == [
        date(2026, 5, 5),
        date(2026, 5, 7),
        date(2026, 5, 8),
    ]


def test_missing_report_dates_returns_today_when_no_reports_exist():
    assert missing_report_dates(set(), date(2026, 5, 30)) == [date(2026, 5, 30)]


def test_existing_report_dates_ignores_non_date_html_files(tmp_path: Path):
    (tmp_path / "2026-05-03.html").write_text("<!doctype html>", encoding="utf-8")
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (tmp_path / "2026-5-4.html").write_text("<!doctype html>", encoding="utf-8")

    assert existing_report_dates(tmp_path) == [date(2026, 5, 3)]
