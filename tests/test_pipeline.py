from argparse import Namespace
from pathlib import Path

from news_bycodex.pipeline import run_report


def test_run_report_with_offline_fixtures(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    sources.write_text(
        """
sources:
  - id: fixture_rss
    name: Fixture RSS
    type: rss
    enabled: true
    url: https://example.com/rss.xml
    credibility: 0.9
    limit: 5
""",
        encoding="utf-8",
    )
    keywords.write_text("keywords:\n  - agent\n", encoding="utf-8")
    args = Namespace(
        date="2026-05-03",
        limit_per_source=5,
        sources=str(sources),
        keywords=str(keywords),
        output_dir=str(tmp_path / "reports"),
        offline_fixtures=True,
    )

    output = run_report(args)

    assert output.exists()
    assert "Agent/AI Trend Report" in output.read_text(encoding="utf-8")
