import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="news-bycodex")
    subcommands = parser.add_subparsers(dest="command", required=True)

    report = subcommands.add_parser("report", help="Generate a daily Agent/AI trend report")
    report.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format")
    report.add_argument("--limit-per-source", type=int, default=10)
    report.add_argument("--sources", default="configs/sources.yaml")
    report.add_argument("--keywords", default="configs/keywords.yaml")
    report.add_argument("--output-dir", default="reports")
    report.add_argument("--offline-fixtures", action="store_true")
    report.add_argument(
        "--use-seen-db",
        action="store_true",
        help="Exclude items already recorded in the local seen-item database.",
    )
    report.add_argument(
        "--codex-agents",
        choices=["off", "review", "full"],
        default="off",
        help="Run Codex-backed editorial subagents: off, review, or full.",
    )
    catch_up = subcommands.add_parser(
        "catch-up",
        help="Generate every missing daily report from the earliest existing report through a date",
    )
    catch_up.add_argument("--through-date", required=True, help="Final date in YYYY-MM-DD format")
    catch_up.add_argument("--limit-per-source", type=int, default=10)
    catch_up.add_argument("--sources", default="configs/sources.yaml")
    catch_up.add_argument("--keywords", default="configs/keywords.yaml")
    catch_up.add_argument("--output-dir", default="reports")
    catch_up.add_argument("--offline-fixtures", action="store_true")
    catch_up.add_argument(
        "--use-seen-db",
        action="store_true",
        help="Exclude items already recorded in the local seen-item database.",
    )
    catch_up.add_argument(
        "--codex-agents",
        choices=["off", "review", "full"],
        default="off",
        help="Run Codex-backed editorial subagents: off, review, or full.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "report":
        from news_bycodex.pipeline import run_report

        run_report(args)
        return 0
    if args.command == "catch-up":
        from news_bycodex.catch_up import run_catch_up_reports

        for output in run_catch_up_reports(args):
            print(output)
        return 0
    return 1
