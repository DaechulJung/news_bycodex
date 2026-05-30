from __future__ import annotations

from argparse import Namespace
from datetime import date
from pathlib import Path

from news_bycodex.pipeline import run_report
from news_bycodex.report_dates import existing_report_dates, missing_report_dates


def report_args_for_date(args: Namespace, report_date: date) -> Namespace:
    return Namespace(
        date=report_date.isoformat(),
        limit_per_source=args.limit_per_source,
        sources=args.sources,
        keywords=args.keywords,
        output_dir=args.output_dir,
        offline_fixtures=args.offline_fixtures,
        use_seen_db=args.use_seen_db,
        codex_agents=args.codex_agents,
    )


def run_catch_up_reports(args: Namespace) -> list[Path]:
    today = date.fromisoformat(args.through_date)
    existing = existing_report_dates(args.output_dir)
    missing = missing_report_dates(existing, today)
    return [run_report(report_args_for_date(args, report_date)) for report_date in missing]
