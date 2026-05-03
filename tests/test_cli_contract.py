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
