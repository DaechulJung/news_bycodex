from news_bycodex.analysis import dedupe_raw_items, normalize_item
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
