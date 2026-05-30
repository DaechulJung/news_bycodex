from argparse import Namespace
from pathlib import Path

from news_bycodex.catch_up import run_catch_up_reports


def make_args(tmp_path: Path) -> Namespace:
    return Namespace(
        through_date="2026-05-06",
        limit_per_source=5,
        sources="configs/sources.yaml",
        keywords="configs/keywords.yaml",
        output_dir=str(tmp_path / "reports"),
        offline_fixtures=False,
        use_seen_db=False,
        codex_agents="full",
    )


def test_run_catch_up_reports_generates_missing_dates_in_order(tmp_path: Path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "2026-05-03.html").write_text("<!doctype html>", encoding="utf-8")
    (reports / "2026-05-05.html").write_text("<!doctype html>", encoding="utf-8")
    generated_dates = []

    def fake_run_report(args):
        generated_dates.append(args.date)
        return Path(args.output_dir) / f"{args.date}.html"

    monkeypatch.setattr("news_bycodex.catch_up.run_report", fake_run_report)

    outputs = run_catch_up_reports(make_args(tmp_path))

    assert generated_dates == ["2026-05-04", "2026-05-06"]
    assert [path.name for path in outputs] == ["2026-05-04.html", "2026-05-06.html"]
