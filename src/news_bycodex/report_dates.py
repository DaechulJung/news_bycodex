from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re


REPORT_FILENAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.html$")


def parse_report_date(path: Path) -> date | None:
    match = REPORT_FILENAME_RE.match(path.name)
    if not match:
        return None
    return date.fromisoformat(match.group("date"))


def existing_report_dates(output_dir: str | Path = "reports") -> list[date]:
    root = Path(output_dir)
    if not root.exists():
        return []
    dates = [parsed for path in root.glob("*.html") if (parsed := parse_report_date(path))]
    return sorted(set(dates))


def missing_report_dates(existing_dates: set[date] | list[date], today: date) -> list[date]:
    existing = set(existing_dates)
    start = min(existing) if existing else today
    missing = []
    current = start
    while current <= today:
        if current not in existing:
            missing.append(current)
        current += timedelta(days=1)
    return missing
