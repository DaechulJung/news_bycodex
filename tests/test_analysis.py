from datetime import datetime, timezone

from news_bycodex.analysis import (
    dedupe_raw_items,
    group_similar_trends,
    impact_from_score,
    normalize_item,
    sort_trends_by_hotness,
    trend_hotness_score,
)
from news_bycodex.models import RawItem, TrendItem


def make_trend(**overrides) -> TrendItem:
    values = {
        "title": "Fixture agent launch",
        "url": "https://example.com/agent",
        "source": "Hacker News",
        "summary": "Released AI agent framework for autonomous coding agent workflows",
        "category": "coding_agent",
        "maturity": "released",
        "impact": "high",
        "signal_strength": 4,
        "why_it_matters": "개발 워크플로에 영향을 줄 수 있습니다.",
    }
    values.update(overrides)
    return TrendItem(**values)


def test_dedupe_raw_items_by_url():
    items = [
        RawItem(
            source_id="hn",
            source_name="HN",
            source_type="hn_algolia",
            title="Agent SDK",
            url="https://example.com/a",
        ),
        RawItem(
            source_id="gh",
            source_name="GitHub",
            source_type="github_search",
            title="Agent SDK",
            url="https://example.com/a",
        ),
    ]

    deduped = dedupe_raw_items(items)

    assert len(deduped) == 1
    assert deduped[0].source_id == "hn"


def test_group_similar_trends_merges_near_duplicates_and_keeps_links():
    trends = [
        make_trend(),
        make_trend(
            title="Fixture agentic framework launch",
            url="https://news.example.com/agent",
            source="GeekNews",
            category="agent_framework",
            signal_strength=3,
        ),
        make_trend(
            title="GPU driver update",
            url="https://example.com/gpu",
            source="Vendor Blog",
            category="tooling",
            signal_strength=2,
        ),
    ]

    grouped = group_similar_trends(trends)

    assert len(grouped) == 2
    agent_group = next(item for item in grouped if item.title == "Fixture agent launch")
    assert agent_group.signal_strength == 4
    assert any("Hacker News: https://example.com/agent" in item for item in agent_group.related_items)
    assert any("GeekNews: https://news.example.com/agent" in item for item in agent_group.related_items)


def test_hotness_ranks_release_keyword_and_related_count_above_plain_signal():
    gpt_release = make_trend(
        title="OpenAI GPT 5.5 model launch",
        url="https://example.com/gpt-55",
        category="model",
        signal_strength=3,
        impact="medium",
        related_items=[
            "YouTube: https://example.com/gpt-55-video",
            "HN: https://example.com/gpt-55-hn",
            "Blog: https://example.com/gpt-55-blog",
        ],
    )
    generic_agent = make_trend(
        title="Generic coding agent framework update",
        url="https://example.com/agent-update",
        signal_strength=4,
        impact="high",
    )

    sorted_trends = sort_trends_by_hotness([generic_agent, gpt_release])

    assert trend_hotness_score(gpt_release) > trend_hotness_score(generic_agent)
    assert sorted_trends[0].title == "OpenAI GPT 5.5 model launch"
    assert sorted_trends[0].hotness_score > 0


def test_sort_trends_by_hotness_handles_missing_and_datetime_publish_dates():
    sorted_trends = sort_trends_by_hotness(
        [
            make_trend(
                title="Undated agent update",
                url="https://example.com/undated",
                published_at=None,
            ),
            make_trend(
                title="Dated agent update",
                url="https://example.com/dated",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
        ]
    )

    assert {trend.title for trend in sorted_trends} == {
        "Undated agent update",
        "Dated agent update",
    }


def test_group_similar_trends_merges_viral_hot_model_variants():
    grouped = group_similar_trends(
        [
            make_trend(
                title="OpenAI GPT 5.5 model launch",
                url="https://example.com/gpt-55-a",
                category="model",
            ),
            make_trend(
                title="GPT 5.5 release for agents",
                url="https://example.com/gpt-55-b",
                category="product",
            ),
            make_trend(
                title="GPT 5.5 launch analysis",
                url="https://example.com/gpt-55-c",
                category="product",
            ),
        ]
    )

    assert len(grouped) == 1
    assert len(grouped[0].related_items) >= 3


def test_normalize_item_scores_coding_agent():
    raw = RawItem(
        source_id="gh",
        source_name="GitHub",
        source_type="github_search",
        title="autonomous coding agent framework",
        url="https://example.com/agent",
        summary="A released coding agent framework for developers",
        metadata={"stars": 250},
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.category == "coding_agent"
    assert trend.maturity == "released"
    assert trend.signal_strength >= 4
    assert "개발" in trend.why_it_matters
    assert "보안" in trend.why_it_matters


def test_normalize_item_uses_korean_brief_why_it_matters():
    raw = RawItem(
        source_id="youtube_fireship",
        source_name="Fireship YouTube",
        source_type="rss",
        title="Codex coding agent update",
        url="https://www.youtube.com/watch?v=fixture",
        summary="A released autonomous coding agent workflow",
    )

    trend = normalize_item(raw, source_credibility=0.75, history_text="")

    assert "개발" in trend.why_it_matters
    assert "This may" not in trend.why_it_matters
    assert "확인" in trend.why_it_matters
    assert len(trend.why_it_matters) <= 150


def test_normalize_item_writes_korean_summary_for_core_trend():
    raw = RawItem(
        source_id="openai_blog",
        source_name="OpenAI",
        source_type="rss",
        title="OpenAI GPT 5.5 model launch",
        url="https://example.com/gpt-55",
        summary="OpenAI launched GPT 5.5 with stronger tool use and coding agent performance.",
    )

    trend = normalize_item(raw, source_credibility=0.95, history_text="")

    assert "GPT 5.5" in trend.summary
    assert "모델" in trend.summary
    assert "성능" in trend.summary
    assert "요금" in trend.why_it_matters
    assert "OpenAI launched" not in trend.summary


def test_normalize_item_generates_clickable_detail_summary_content():
    raw = RawItem(
        source_id="openai_news",
        source_name="OpenAI News",
        source_type="rss",
        title="Running Codex safely at OpenAI",
        url="https://openai.com/index/running-codex-safely",
        summary=(
            "OpenAI shared how it runs Codex with sandboxing, approval policies, "
            "network controls, and agent-native telemetry."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.95, history_text="")

    assert trend.detail_summary
    assert "핵심 정리" in trend.detail_summary
    assert "OpenAI News" in trend.detail_summary
    assert "Running Codex safely at OpenAI" in trend.detail_summary
    assert "확인 포인트" in trend.detail_summary


def test_detail_summary_preserves_source_content_details_not_category_filler():
    raw = RawItem(
        source_id="hn",
        source_name="Hacker News",
        source_type="hn_algolia",
        title="Show HN: Speq - A collaborative web-based repository for your product's spec",
        url="https://getspeq.com",
        summary=(
            "Speq is a collaborative web-based repository for your product's specification. "
            "It peppers you with questions about your new project until it understands what "
            "you are trying to build. Then it puts everything together into a comprehensive "
            "Speq that can become a PRD, be shared with colleagues, or be handed off to an "
            "agent to build via MCP. Speq helps define vision, navigation flow, product "
            "requirements, logic, and tech requirements. It is easy to edit, version, and "
            "evolve over time. Thanks to Microsoft's support, the tool is free for now."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert "원문 상세 요약" in trend.detail_summary
    assert "질문" in trend.detail_summary
    assert "PRD" in trend.detail_summary
    assert "MCP" in trend.detail_summary
    assert "비전" in trend.detail_summary
    assert "navigation flow" in trend.detail_summary
    assert "편집" in trend.detail_summary
    assert "버전" in trend.detail_summary
    assert "Microsoft" in trend.detail_summary
    assert "코딩 에이전트의 실행 방식" not in trend.detail_summary


def test_normalize_item_summarizes_specific_news_facts_not_generic_category_text():
    raw = RawItem(
        source_id="geeknews",
        source_name="GeekNews",
        source_type="rss",
        title="Codex CLI 에 /goal 기능 추가",
        url="https://news.hada.io/topic?id=29158",
        summary=(
            "0.128.0 버전에서 목표 기반 자동 반복 실행 기능인 /goal 기능이 추가됨. "
            "Ralph loop 개념을 Codex CLI에 적용한 것으로, 설정한 목표가 완료될 때까지 "
            "명령을 반복 실행함."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert "/goal" in trend.summary
    assert "0.128.0" in trend.summary
    assert "목표 기반 자동 반복 실행" in trend.summary
    assert "코딩 에이전트와 개발 자동화 관련 신호입니다" not in trend.summary
    assert "/goal" in trend.why_it_matters
    assert "종료 조건" in trend.why_it_matters


def test_normalize_item_summarizes_youtube_news_title_instead_of_channel_promo():
    raw = RawItem(
        source_id="youtube_jocoding",
        source_name="JoCoding YouTube",
        source_type="rss",
        title="IT뉴스 - Google 신모델, Claude 요금 논란, Codex goal, Grok 4.3 API 등",
        url="https://www.youtube.com/watch?v=fixture",
        summary=(
            "출처 모아보기 조코딩과 코딩 공부하기 제보 메일: jebo@jocoding.net. "
            "조코딩 바이브 코딩 1인 창업 무료 강의. 목차 00:00 구글 Gemini 신모델 "
            "05:12 Claude 요금 논란 08:20 Codex goal"
        ),
    )

    trend = normalize_item(raw, source_credibility=0.75, history_text="")

    assert "Google 신모델" in trend.summary
    assert "Claude 요금 논란" in trend.summary
    assert "Codex goal" in trend.summary
    assert "출처 모아보기" not in trend.summary
    assert "제보 메일" not in trend.summary
    assert "무료 강의" not in trend.summary


def test_normalize_item_adds_hash_tags_and_column_ready_tag_flags():
    raw = RawItem(
        source_id="openai_blog",
        source_name="OpenAI",
        source_type="rss",
        title="OpenAI GPT 5.5 model launch",
        url="https://example.com/gpt-55",
        summary="OpenAI launched GPT 5.5 with stronger tool use and coding agent performance.",
    )

    trend = normalize_item(raw, source_credibility=0.95, history_text="")

    assert "#model" in trend.tags
    assert "#openai" in trend.tags
    assert "#release" in trend.tags
    assert "#coding_agent" in trend.tags
    assert trend.tag_flags["model"] is True
    assert trend.tag_flags["openai"] is True
    assert trend.tag_flags["anthropic"] is False


def test_normalize_item_tags_codex_as_openai_coding_agent():
    raw = RawItem(
        source_id="geeknews",
        source_name="GeekNews",
        source_type="rss",
        title="Codex CLI 에 /goal 기능 추가",
        url="https://news.hada.io/topic?id=29158",
        summary="목표 기반 자동 반복 실행 기능이 Codex CLI에 추가됨.",
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert "#coding_agent" in trend.tags
    assert "#openai" in trend.tags
    assert "#cli" in trend.tags
    assert "#workflow" in trend.tags
    assert trend.tag_flags["coding_agent"] is True
    assert trend.tag_flags["workflow"] is True


def test_normalize_item_classifies_agent_harness_engineering_signal():
    raw = RawItem(
        source_id="langchain_blog",
        source_name="LangChain Blog",
        source_type="rss",
        title="Agent harness runtime adds subagent orchestration and eval observability",
        url="https://www.langchain.com/blog/agent-harness-runtime",
        summary=(
            "A production agent harness release adds durable execution, subagent routing, "
            "tool calling, evaluation, tracing, and observability for long-running agents."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.9, history_text="")

    assert trend.category == "harness_engineering"
    assert trend.signal_strength >= 4
    assert "#harness_engineering" in trend.tags
    assert "#agentic" in trend.tags
    assert "#orchestration" in trend.tags
    assert "#subagent" in trend.tags
    assert "#evaluation" in trend.tags
    assert "#observability" in trend.tags
    assert "#tool_use" in trend.tags
    assert "하네스" in trend.summary
    assert "평가" in trend.why_it_matters
    assert "관찰성" in trend.why_it_matters


def test_normalize_item_handles_hn_harness_demo_without_model_release_overreach():
    raw = RawItem(
        source_id="hacker_news",
        source_name="Hacker News Algolia",
        source_type="hn_algolia",
        title="Show HN: ByAllo - the online bookstore that runs itself",
        url="https://byallo.com/",
        summary=(
            "Under the hood: byallo.com is a small repo with a simple UI sitting on top of "
            "Momental - an agent harness with a self-maintaining context graph. A team of "
            "custom-built cloud agents running on Claude, Grok, or Gemini depending on the "
            "task form their own strategy, update their own plan, and hand off to a human "
            "teammate over MCP."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.category == "harness_engineering"
    assert "Momental" in trend.summary
    assert "모델 업데이트" not in trend.summary
    assert trend.tag_flags["harness_engineering"] is True
    assert trend.tag_flags["mcp"] is True
    assert trend.tag_flags["model"] is False
    assert trend.tag_flags["anthropic"] is False
    assert trend.tag_flags["google"] is False
    assert trend.tag_flags["xai"] is False


def test_normalize_item_does_not_tag_google_for_google_search_aggregator():
    raw = RawItem(
        source_id="google_search",
        source_name="Google Search",
        source_type="google_search",
        title="하네스 엔지니어링으로 AI 에이전트를 길들여봤습니다 - 요즘IT",
        url="https://news.google.com/rss/articles/example",
        summary="하네스 엔지니어링과 AI 에이전트 운영 환경을 설명한 기사입니다.",
    )

    trend = normalize_item(raw, source_credibility=0.7, history_text="")

    assert trend.tag_flags["harness_engineering"] is True
    assert trend.tag_flags["google"] is False
    assert "#google" not in trend.tags


def test_normalize_item_matches_provider_tags_as_entities_not_substrings():
    raw = RawItem(
        source_id="llamaindex_blog",
        source_name="LlamaIndex Blog",
        source_type="rss",
        title="LlamaParse MCP: Agentic OCR tools for your AI agents",
        url="https://www.llamaindex.ai/blog/llamaparse-mcp",
        summary="The metadata and teammate handoff flow improves document agents.",
    )

    trend = normalize_item(raw, source_credibility=0.85, history_text="")

    assert trend.tag_flags["meta"] is False
    assert "#meta" not in trend.tags


def test_normalize_item_classifies_open_model_agent_eval_as_model_not_harness():
    raw = RawItem(
        source_id="langchain_blog",
        source_name="LangChain Blog",
        source_type="rss",
        title="Open Models have crossed a threshold",
        url="https://www.langchain.com/blog/open-models-have-crossed-a-threshold",
        summary=(
            "Open models like GLM-5 and MiniMax M2.7 now match closed frontier models "
            "on core agent tasks, file operations, tool use, and instruction following."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.85, history_text="")

    assert trend.category == "model"
    assert trend.tag_flags["model"] is True


def test_normalize_item_classifies_ai_workstation_as_tooling_not_model():
    raw = RawItem(
        source_id="youtube_jocoding",
        source_name="JoCoding YouTube",
        source_type="rss",
        title="HP의 괴물 AI 워크스테이션 4대 연결한 역대급 세팅ㄷㄷ 데이터센터급 모델 돌아갑니다",
        url="https://www.youtube.com/watch?v=fixture",
        summary=(
            "HP ZGX nano AI station 특징, 원격 연결, 4대 클러스터링, GLM 5.1 실행을 "
            "다루는 워크스테이션 소개 영상입니다."
        ),
    )

    trend = normalize_item(raw, source_credibility=0.7, history_text="")

    assert trend.category == "tooling"
    assert trend.tag_flags["model"] is False
    assert "#model" not in trend.tags


def test_harness_engineering_hotness_beats_plain_agent_update():
    harness = make_trend(
        title="Agent harness runtime release adds eval observability",
        url="https://example.com/harness",
        category="harness_engineering",
        signal_strength=3,
        impact="high",
    )
    plain = make_trend(
        title="Generic agent article",
        url="https://example.com/plain-agent",
        category="agent_framework",
        signal_strength=3,
        impact="high",
    )

    assert trend_hotness_score(harness) > trend_hotness_score(plain)


def test_normalize_item_summarizes_long_html_body_for_report():
    raw = RawItem(
        source_id="hn",
        source_name="Hacker News",
        source_type="hn_algolia",
        title="Show HN: Speq - A collaborative web-based repository for your product's spec",
        url="https://getspeq.com",
        summary=(
            "Hey HN!<p>My friend and I made and just launched Speq: "
            "A collaborative web-based repository for your product&#x27;s specification. "
            "It peppers you with questions about your new project until the goal is clear. "
            "Then we put everything together into a comprehensive Speq "
            "(see an actual example here: https://getspeq.com/#anatomy) "
            "that you can then turn into a PRD, share with colleagues to evaluate and collaborate "
            "on, or hand off to an agent to build via MCP."
            "<p>We both left our Fortune 500 Eng Leadership roles last year. "
            '<a href="https://getspeq.com/#anatomy">example</a>'
        ),
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert "<p>" not in trend.summary
    assert "<a" not in trend.summary
    assert "&#x27;" not in trend.summary
    assert "https://getspeq.com" not in trend.summary
    assert "Hey HN" not in trend.summary
    assert "Speq" in trend.summary
    assert "제품 명세" in trend.summary
    assert "MCP" in trend.summary
    assert "에이전트" in trend.summary
    assert "product's specification" not in trend.summary
    assert "peppers you with questions" not in trend.summary
    assert "see an actual example" not in trend.summary
    assert "모델 성능" not in trend.why_it_matters
    assert "확인" in trend.why_it_matters
    assert len(trend.summary) <= 260


def test_normalize_item_carries_image_url_metadata():
    raw = RawItem(
        source_id="youtube",
        source_name="YouTube",
        source_type="rss",
        title="Agent framework video",
        url="https://www.youtube.com/watch?v=example",
        summary="Released AI agent framework demo",
        metadata={"image_url": "https://i.ytimg.com/vi/example/hqdefault.jpg"},
    )

    trend = normalize_item(raw, source_credibility=0.7, history_text="")

    assert trend.image_url == "https://i.ytimg.com/vi/example/hqdefault.jpg"


def test_dedupe_raw_items_by_canonical_url():
    items = [
        RawItem(
            source_id="hn",
            source_name="HN",
            source_type="hn_algolia",
            title="Agent SDK",
            url="http://example.com/a/?utm_source=hn#comments",
        ),
        RawItem(
            source_id="web",
            source_name="Web",
            source_type="web",
            title="Agent SDK",
            url="https://example.com/a",
        ),
        RawItem(
            source_id="arxiv_abs",
            source_name="arXiv",
            source_type="arxiv",
            title="Agent Paper",
            url="https://arxiv.org/abs/2601.12345",
        ),
        RawItem(
            source_id="arxiv_pdf",
            source_name="arXiv",
            source_type="arxiv",
            title="Agent Paper PDF",
            url="https://arxiv.org/pdf/2601.12345.pdf?utm_campaign=agent#page=1",
        ),
    ]

    deduped = dedupe_raw_items(items)

    assert len(deduped) == 2
    assert {item.source_id for item in deduped} == {"hn", "arxiv_abs"}


def test_dedupe_raw_items_selects_better_canonical_duplicate_and_records_evidence():
    items = [
        RawItem(
            source_id="web",
            source_name="Web",
            source_type="web",
            title="Agent SDK",
            url="http://example.com/a?utm_source=web",
        ),
        RawItem(
            source_id="gh",
            source_name="GitHub",
            source_type="github_search",
            title="Agent SDK",
            url="https://example.com/a/",
            summary="A detailed release summary for developers",
            metadata={"stars": 120},
        ),
    ]

    deduped = dedupe_raw_items(items)

    assert len(deduped) == 1
    assert deduped[0].source_id == "gh"
    assert deduped[0].metadata["duplicate_count"] == 2
    assert deduped[0].metadata["duplicate_sources"] == ["web", "gh"]
    assert deduped[0].metadata["stars"] == 120


def test_normalize_item_uses_cautious_maturity_fallback():
    raw = RawItem(
        source_id="web",
        source_name="Web",
        source_type="web",
        title="New agent architecture discussion",
        url="https://example.com/agent-architecture",
    )

    trend = normalize_item(raw, source_credibility=0.5, history_text="")

    assert trend.maturity == "prototype"


def test_normalize_item_classifies_research_as_prototype():
    raw = RawItem(
        source_id="arxiv",
        source_name="arXiv",
        source_type="arxiv",
        title="arXiv paper proposes an agent benchmark",
        url="https://arxiv.org/abs/2601.12345",
    )

    trend = normalize_item(raw, source_credibility=0.7, history_text="")

    assert trend.maturity == "prototype"


def test_impact_from_score_thresholds():
    assert impact_from_score(5) == "strategic"
    assert impact_from_score(4) == "high"
    assert impact_from_score(3) == "medium"
    assert impact_from_score(2) == "low"


def test_normalize_item_handles_numeric_string_star_metadata():
    raw = RawItem(
        source_id="gh",
        source_name="GitHub",
        source_type="github_search",
        title="coding agent framework",
        url="https://example.com/agent",
        summary="A released coding agent framework",
        metadata={"stars": "250"},
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.signal_strength == 5


def test_normalize_item_ignores_none_star_metadata():
    raw = RawItem(
        source_id="gh",
        source_name="GitHub",
        source_type="github_search",
        title="coding agent framework",
        url="https://example.com/agent",
        summary="A released coding agent framework",
        metadata={"stars": None},
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.signal_strength == 4


def test_normalize_item_ignores_malformed_star_metadata():
    raw = RawItem(
        source_id="gh",
        source_name="GitHub",
        source_type="github_search",
        title="coding agent framework",
        url="https://example.com/agent",
        summary="A released coding agent framework",
        metadata={"stars": "many"},
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.signal_strength == 4
