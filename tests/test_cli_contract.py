from news_bycodex.cli import build_parser


def test_cli_accepts_date_and_limit_arguments():
    parser = build_parser()
    args = parser.parse_args(
        [
            "report",
            "--date",
            "2026-05-03",
            "--limit-per-source",
            "3",
        ]
    )

    assert args.command == "report"
    assert args.date == "2026-05-03"
    assert args.limit_per_source == 3
    assert args.use_seen_db is False


def test_cli_enables_seen_db_only_when_requested():
    parser = build_parser()
    args = parser.parse_args(
        [
            "report",
            "--date",
            "2026-05-03",
            "--use-seen-db",
        ]
    )

    assert args.use_seen_db is True


def test_cli_accepts_codex_agents_full_mode():
    parser = build_parser()
    args = parser.parse_args(
        [
            "report",
            "--date",
            "2026-05-03",
            "--codex-agents",
            "full",
        ]
    )

    assert args.codex_agents == "full"


def test_cli_accepts_catch_up_report_generation_arguments():
    parser = build_parser()
    args = parser.parse_args(
        [
            "catch-up",
            "--through-date",
            "2026-05-30",
            "--output-dir",
            "reports",
            "--codex-agents",
            "full",
        ]
    )

    assert args.command == "catch-up"
    assert args.through_date == "2026-05-30"
    assert args.output_dir == "reports"
    assert args.codex_agents == "full"
