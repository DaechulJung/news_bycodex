from news_bycodex.analysis import dedupe_raw_items, impact_from_score, normalize_item
from news_bycodex.models import RawItem


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
    assert "developer" in trend.why_it_matters.lower()


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
