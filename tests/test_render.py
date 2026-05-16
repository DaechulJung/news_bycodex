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
    assert "수집 범위" in html
    assert "HTTP 429" in html
    assert "핵심 요약" in html
    assert "Why it matters" not in html


def test_render_report_shows_related_news_links(tmp_path: Path):
    report = make_report(
        top_trends=[
            make_item(
                related_items=[
                    "duplicate_count=2",
                    "Hacker News: https://example.com/codex",
                    "GeekNews: https://news.example.com/codex",
                ]
            )
        ],
        weak_signals=[
            make_item(
                title="Weak grouped signal",
                url="https://example.com/weak",
                related_items=["Community: https://weak.example.com/codex"],
            )
        ],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "Codex agent harness - 근거 및 관련 링크" in html
    assert "Weak grouped signal - 근거 및 관련 링크" in html
    assert "같은 트렌드의 추가 원문" not in html
    assert 'href="https://example.com/codex"' in html
    assert html.count('href="https://example.com/codex"') == 1
    assert 'href="https://news.example.com/codex"' in html
    assert 'href="https://weak.example.com/codex"' in html
    assert "duplicate_count=2" not in html


def test_render_report_deduplicates_related_news_links_by_url(tmp_path: Path):
    report = make_report(
        top_trends=[
            make_item(
                related_items=[
                    "Papers with Code Latest: https://paperswithcode.com/papers/agent",
                    "Papers with Code Latest: https://paperswithcode.com/papers/agent",
                    "Mirror: https://paperswithcode.com/papers/agent?utm_source=feed",
                    "JoCoding YouTube: https://www.youtube.com/watch?v=abc",
                    "JoCoding YouTube: https://www.youtube.com/watch?v=abc",
                ]
            )
        ]
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert html.count('href="https://paperswithcode.com/papers/agent"') == 1
    assert html.count('href="https://www.youtube.com/watch?v=abc"') == 1


def test_render_report_hides_self_only_related_links_for_weak_signals(tmp_path: Path):
    report = make_report(
        top_trends=[],
        weak_signals=[
            make_item(
                title="Meta AI",
                url="https://paperswithcode.com/AI-at-Meta",
                source="Papers with Code Latest",
                related_items=[
                    "Papers with Code Latest: https://paperswithcode.com/AI-at-Meta",
                    "Papers with Code Latest: https://paperswithcode.com/AI-at-Meta",
                ],
            )
        ],
        source_errors=[],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "근거 및 관련 링크" not in html
    assert html.count("Papers with Code Latest") == 1


def test_render_report_shows_one_line_summary_for_weak_signals(tmp_path: Path):
    report = make_report(
        top_trends=[],
        weak_signals=[
            make_item(
                title="Claude Code plugin guide",
                source="GymCoding YouTube",
                signal_strength=2,
                summary="Claude Code 공식 플러그인 4개로 토큰 사용량을 줄이는 실무 하네스 내용입니다.",
            )
        ],
        source_errors=[],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "Claude Code plugin guide" in html
    assert (
        "- Claude Code 공식 플러그인 4개로 토큰 사용량을 줄이는 실무 하네스 내용입니다."
        in html
    )
    assert "요약:" not in html


def test_render_report_uses_horizontal_trend_cards_with_image_and_insight(tmp_path: Path):
    report = make_report(
        top_trends=[
            make_item(
                image_url="https://example.com/thumb.jpg",
                title="Agent framework launch",
                summary="A concise report summary.",
                why_it_matters="Agent workflows may change.",
                tags=["#coding_agent", "#openai"],
            )
        ]
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert 'class="trend-card"' in html
    assert 'data-layout="horizontal"' in html
    assert 'class="trend-image"' in html
    assert 'src="https://example.com/thumb.jpg"' in html
    assert 'class="trend-content"' in html
    assert 'class="trend-insight"' in html
    assert "A concise report summary." in html
    assert "Agent workflows may change." in html
    assert "#coding_agent" in html
    assert "#openai" in html


def test_render_report_makes_summary_clickable_with_korean_detail(tmp_path: Path):
    report = make_report(
        top_trends=[
            make_item(
                title="Running Codex safely at OpenAI",
                summary=(
                    "OpenAI가 Codex 운영에서 sandboxing, approval, network policy, "
                    "agent-native telemetry를 공개했습니다."
                ),
                detail_summary=(
                    "핵심 정리\n"
                    "- OpenAI가 Codex 운영 안전장치를 설명했습니다.\n"
                    "- sandboxing, 승인 흐름, 네트워크 정책, telemetry가 핵심입니다.\n\n"
                    "확인 포인트\n"
                    "- 실제 운영 하네스에 어떤 정책을 적용할지 점검하세요."
                ),
            )
        ],
        weak_signals=[
            make_item(
                title="Weak Codex signal",
                url="https://example.com/weak-codex",
                summary="Codex 관련 약한 관찰 신호입니다.",
                detail_summary="핵심 정리\n- 약한 신호지만 후속 확인이 필요합니다.",
            )
        ],
        deferred_items=[
            make_item(
                title="Deferred Codex signal",
                url="https://example.com/deferred-codex",
                summary="보류된 Codex 관찰 신호입니다.",
                detail_summary="핵심 정리\n- 보류 항목도 상세 확인이 가능합니다.",
            )
        ],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert 'class="trend-detail"' in html
    assert "<summary>OpenAI가 Codex 운영에서 sandboxing" in html
    assert "OpenAI가 Codex 운영 안전장치를 설명했습니다." in html
    assert "실제 운영 하네스에 어떤 정책을 적용할지 점검하세요." in html
    assert "<summary>Codex 관련 약한 관찰 신호입니다.</summary>" in html
    assert "약한 신호지만 후속 확인이 필요합니다." in html
    assert "<summary>보류된 Codex 관찰 신호입니다.</summary>" in html
    assert "보류 항목도 상세 확인이 가능합니다." in html


def test_render_report_does_not_expand_raw_html_summaries(tmp_path: Path):
    long_html_summary = (
        "Hey HN!<p>My friend and I launched Speq: a collaborative specification repository. "
        "It can produce PRDs and hand off requirements to coding agents via MCP. "
        '<a href="https://example.com">example</a> '
        + "extra details " * 80
    )
    report = make_report(top_trends=[make_item(summary=long_html_summary)])

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert "Hey HN" not in html
    assert "&lt;p&gt;" not in html
    assert "&lt;a href" not in html
    assert "extra details extra details extra details extra details" not in html


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
    assert "&lt;img" not in html
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
    assert "이번 실행에서 승격된 핵심 트렌드가 없습니다." in html
    assert '<div class="grid">' not in html
