from datetime import datetime, timezone
from pathlib import Path

from news_bycodex.models import ReportData, TrendItem
from news_bycodex.render import render_report


def test_render_report_writes_html(tmp_path: Path):
    item = TrendItem(
        title="Codex agent harness",
        url="https://example.com/codex",
        source="Hacker News",
        summary="A harness for agent trend reports",
        category="coding_agent",
        maturity="released",
        impact="high",
        signal_strength=4,
        why_it_matters="This may affect developer workflows.",
    )
    report = ReportData(
        date="2026-05-03",
        generated_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        executive_summary="One strong coding-agent signal.",
        top_trends=[item],
        weak_signals=[],
        deferred_items=[],
        source_errors=[{"source_id": "reddit", "message": "HTTP 429"}],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert output.name == "2026-05-03.html"
    assert "Codex agent harness" in html
    assert "Source Coverage" in html
    assert "HTTP 429" in html
