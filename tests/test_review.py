from datetime import datetime, timezone

from news_bycodex.models import ReportData, TrendItem
from news_bycodex.review import final_review_report


def make_item(**overrides) -> TrendItem:
    values = {
        "title": "Codex CLI 에 /goal 기능 추가",
        "url": "https://example.com/codex-goal",
        "source": "GeekNews",
        "summary": "Agent/AI 생태계에서 관찰된 신호입니다.",
        "category": "coding_agent",
        "maturity": "released",
        "impact": "high",
        "signal_strength": 4,
        "tags": ["#coding_agent", "#openai", "#cli"],
        "tag_flags": {"coding_agent": True, "openai": True, "cli": True},
        "why_it_matters": "초기 신호입니다.",
    }
    values.update(overrides)
    return TrendItem(**values)


def make_report(**overrides) -> ReportData:
    values = {
        "date": "2026-05-05",
        "generated_at": datetime(2026, 5, 5, tzinfo=timezone.utc),
        "executive_summary": "핵심 트렌드 1건을 정리했습니다.",
        "top_trends": [make_item()],
        "weak_signals": [],
        "deferred_items": [],
        "source_errors": [],
    }
    values.update(overrides)
    return ReportData(**values)


def test_final_reviewer_requests_revision_and_applies_fix_for_generic_item():
    report = make_report()

    reviewed_report, reviews = final_review_report(report)

    item = reviewed_report.top_trends[0]
    assert item.quality_score >= 3
    assert "summary_too_generic" in item.revision_requests
    assert "insight_too_generic" in item.revision_requests
    assert "/goal" in item.summary
    assert "종료 조건" in item.why_it_matters
    assert reviews[0]["reviewer"] == "final_reviewer"
    assert reviews[0]["requested_from"] == "Trend Analyst"
    assert reviews[0]["status"] == "fixed"


def test_final_reviewer_passes_specific_well_tagged_item_without_revision():
    report = make_report(
        top_trends=[
            make_item(
                summary="Codex CLI 0.128.0에 /goal 기능이 추가되어 목표 기반 자동 반복 실행을 지원합니다.",
                why_it_matters=(
                    "/goal 기능은 긴 코딩 작업의 자동 반복 범위를 넓힙니다. 종료 조건, 실패 복구, "
                    "사람 리뷰 시점을 확인해야 합니다."
                ),
            )
        ]
    )

    reviewed_report, reviews = final_review_report(report)

    item = reviewed_report.top_trends[0]
    assert item.quality_score == 5
    assert item.revision_requests == []
    assert reviews[0]["status"] == "approved"


def test_final_reviewer_routes_corroboration_request_to_collector():
    report = make_report(
        top_trends=[
            make_item(
                source="GymCoding YouTube",
                summary="Claude Code 플러그인 사용 방식과 토큰 절약 흐름을 실무 하네스 관점에서 설명한 영상입니다.",
                why_it_matters=(
                    "YouTube 단독 신호라도 실무 채택 가능성이 높으면 공식 문서나 보조 출처를 확인해 "
                    "도구 안정성, 보안 권한, 비용 절감 효과를 분리해서 검증해야 합니다."
                ),
            )
        ]
    )

    reviewed_report, reviews = final_review_report(report)

    item = reviewed_report.top_trends[0]
    assert "needs_corroboration" in item.revision_requests
    assert reviews[0]["requested_from"] == "Collector Agent"
    assert reviews[0]["requested_roles"] == ["Collector Agent"]
