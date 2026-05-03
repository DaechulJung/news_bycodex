from datetime import datetime, timezone
from pathlib import Path

from news_bycodex.models import ReportData, TrendItem
from news_bycodex.render import render_report


def make_item(**overrides) -> TrendItem:
    values = {
        "title": "Codex agent harness",
        "url": "https://example.com/codex",
        "source": "Hacker News",
        "summary": "A harness for agent trend reports",
        "category": "coding_agent",
        "maturity": "released",
        "impact": "high",
        "signal_strength": 4,
        "why_it_matters": "This may affect developer workflows.",
    }
    values.update(overrides)
    return TrendItem(**values)


def make_report(**overrides) -> ReportData:
    item = make_item()
    values = {
        "date": "2026-05-03",
        "generated_at": datetime(2026, 5, 3, tzinfo=timezone.utc),
        "executive_summary": "One strong coding-agent signal.",
        "top_trends": [item],
        "weak_signals": [],
        "deferred_items": [],
        "source_errors": [{"source_id": "reddit", "message": "HTTP 429"}],
    }
    values.update(overrides)
    return ReportData(**values)


def test_render_report_writes_html(tmp_path: Path):
    report = make_report()

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert output.name == "2026-05-03.html"
    assert "Codex agent harness" in html
    assert "Source Coverage" in html
    assert "HTTP 429" in html


def test_render_report_sanitizes_unsafe_item_urls(tmp_path: Path):
    report = make_report(
        top_trends=[make_item(url="javascript:alert(1)")],
        weak_signals=[make_item(title="Weak signal", url="mailto:team@example.com")],
        deferred_items=[make_item(title="Deferred item", url="ftp://example.com/item")],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert 'href="javascript:alert(1)"' not in html
    assert 'href="mailto:team@example.com"' not in html
    assert 'href="ftp://example.com/item"' not in html
    assert html.count('href="#"') == 3


def test_render_report_escapes_item_text(tmp_path: Path):
    report = make_report(
        top_trends=[
            make_item(
                title='<script>alert("title")</script>',
                summary='<img src=x onerror="alert(1)">',
            )
        ],
        executive_summary='<strong onclick="alert(1)">summary</strong>',
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "<img" not in html
    assert "<strong onclick" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html
    assert "&lt;strong" in html


def test_render_report_shows_empty_top_trends_fallback(tmp_path: Path):
    report = ReportData(
        date="2026-05-03",
        generated_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        executive_summary="No promoted signals.",
        top_trends=[],
        weak_signals=[],
        deferred_items=[],
        source_errors=[],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "No top trends were promoted in this run." in html
    assert '<div class="grid">' not in html
