from __future__ import annotations

from news_bycodex.analysis import clean_report_text, clean_report_title, truncate_text
from news_bycodex.models import ReportData, TrendItem


GENERIC_SUMMARY_MARKERS = (
    "Agent/AI 생태계에서 관찰된 신호입니다",
    "후속 관찰이 필요한 초기 신호",
    "코딩 에이전트와 개발 자동화 관련 신호입니다",
)
GENERIC_INSIGHT_MARKERS = (
    "초기 신호입니다",
    "영향을 줄 수 있습니다",
)


def final_review_report(report: ReportData) -> tuple[ReportData, list[dict[str, object]]]:
    reviewer = FinalReviewerAgent()
    reviewed_top, top_reviews = reviewer.review_items(report.top_trends, section="top_trends")
    reviewed_weak, weak_reviews = reviewer.review_items(report.weak_signals, section="weak_signals")
    reviewed_deferred, deferred_reviews = reviewer.review_items(
        report.deferred_items, section="deferred_items"
    )
    reviews = top_reviews + weak_reviews + deferred_reviews
    return (
        report.model_copy(
            update={
                "top_trends": reviewed_top,
                "weak_signals": reviewed_weak,
                "deferred_items": reviewed_deferred,
                "editorial_reviews": reviews,
            }
        ),
        reviews,
    )


class FinalReviewerAgent:
    reviewer_id = "final_reviewer"

    def review_items(
        self, items: list[TrendItem], section: str
    ) -> tuple[list[TrendItem], list[dict[str, object]]]:
        reviewed_items: list[TrendItem] = []
        reviews: list[dict[str, object]] = []
        for item in items:
            reviewed_item, review = self.review_item(item, section)
            reviewed_items.append(reviewed_item)
            reviews.append(review)
        return reviewed_items, reviews

    def review_item(self, item: TrendItem, section: str) -> tuple[TrendItem, dict[str, object]]:
        requests = revision_requests(item)
        notes = review_notes(item, requests)
        revised = apply_revision_requests(item, requests)
        quality_score = score_quality(revised, requests)
        status = "fixed" if requests else "approved"
        reviewed_item = revised.model_copy(
            update={
                "quality_score": quality_score,
                "revision_requests": requests,
                "review_notes": notes,
            }
        )
        return reviewed_item, review_record(reviewed_item, section, requests, notes, status)


def revision_requests(item: TrendItem) -> list[str]:
    requests: list[str] = []
    if is_generic_summary(item.summary) or len(clean_report_text(item.summary)) < 35:
        requests.append("summary_too_generic")
    if is_generic_insight(item.why_it_matters) or len(clean_report_text(item.why_it_matters)) < 35:
        requests.append("insight_too_generic")
    if not item.tags:
        requests.append("missing_tags")
    if item.signal_strength >= 3 and not item.related_items and item.source.lower().endswith("youtube"):
        requests.append("needs_corroboration")
    return requests


def is_generic_summary(summary: str) -> bool:
    return any(marker in summary for marker in GENERIC_SUMMARY_MARKERS)


def is_generic_insight(insight: str) -> bool:
    return any(marker in insight for marker in GENERIC_INSIGHT_MARKERS)


def review_notes(item: TrendItem, requests: list[str]) -> list[str]:
    notes: list[str] = []
    if "summary_too_generic" in requests:
        notes.append("요약이 뉴스 고유 사실보다 카테고리 설명에 가깝습니다.")
    if "insight_too_generic" in requests:
        notes.append("인사이트가 도입 판단 기준이나 확인 포인트를 더 제시해야 합니다.")
    if "missing_tags" in requests:
        notes.append("DB 컬럼화를 위한 태그 분류가 필요합니다.")
    if "needs_corroboration" in requests:
        notes.append("YouTube 단독 강한 신호는 원문 또는 보조 출처 확인이 필요합니다.")
    return notes


def apply_revision_requests(item: TrendItem, requests: list[str]) -> TrendItem:
    updates: dict[str, object] = {}
    if "summary_too_generic" in requests:
        updates["summary"] = editor_requested_summary(item)
    if "insight_too_generic" in requests:
        updates["why_it_matters"] = editor_requested_insight(item)
    if "missing_tags" in requests:
        updates["tags"] = [f"#{item.category}"]
        updates["tag_flags"] = {item.category: True}
    return item.model_copy(update=updates) if updates else item


def editor_requested_summary(item: TrendItem) -> str:
    title = clean_report_title(item.title)
    if "/goal" in title.lower():
        return f"{title}: 목표 기반 자동 반복 실행 기능으로 긴 코딩 작업을 이어가는 Codex CLI 업데이트입니다."
    if "plugin" in title.lower() or "플러그인" in title:
        return f"{title}: 공식 플러그인 활용과 토큰 절약 방식을 다룬 실무형 코딩 에이전트 콘텐츠입니다."
    return truncate_text(f"{title}: 원문에서 확인된 Agent/AI 관련 업데이트입니다.", 220)


def editor_requested_insight(item: TrendItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    if "/goal" in text:
        return (
            "/goal 기능은 에이전트가 목표 달성까지 반복 실행하는 범위를 넓힙니다. "
            "종료 조건, 실패 복구, 사람 리뷰 시점을 확인해야 합니다."
        )
    if "plugin" in text or "플러그인" in text:
        return (
            "플러그인 기반 확장은 코딩 에이전트 운영 비용과 컨텍스트 사용량에 직접 영향을 줍니다. "
            "토큰 절감 효과와 보안 권한 범위를 함께 점검하세요."
        )
    return (
        "제품 또는 워크플로 도입 전에 원문 근거, 실제 사용 사례, 비용과 보안 영향을 "
        "함께 확인해야 합니다."
    )


def score_quality(item: TrendItem, requests: list[str]) -> int:
    score = 5
    score -= len(requests)
    if len(item.summary) < 40:
        score -= 1
    if len(item.why_it_matters) < 40:
        score -= 1
    if not item.tags:
        score -= 1
    return max(1, min(5, score))


def review_record(
    item: TrendItem,
    section: str,
    requests: list[str],
    notes: list[str],
    status: str,
) -> dict[str, object]:
    roles = requested_roles(requests)
    return {
        "reviewer": FinalReviewerAgent.reviewer_id,
        "section": section,
        "title": item.title,
        "url": item.url,
        "quality_score": item.quality_score,
        "status": status,
        "requested_from": roles[0] if roles else "",
        "requested_roles": roles,
        "revision_requests": requests,
        "notes": notes,
    }


def requested_roles(requests: list[str]) -> list[str]:
    role_by_request = {
        "summary_too_generic": "Trend Analyst",
        "insight_too_generic": "Trend Analyst",
        "missing_tags": "Trend Analyst",
        "needs_corroboration": "Collector Agent",
    }
    roles: list[str] = []
    for request in requests:
        role = role_by_request.get(request)
        if role and role not in roles:
            roles.append(role)
    return roles
