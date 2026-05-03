from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import httpx

from news_bycodex.analysis import canonical_url, dedupe_raw_items, normalize_item
from news_bycodex.collectors.api import (
    collect_arxiv,
    collect_github_search,
    collect_hn_algolia,
    collect_reddit_json,
)
from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.collectors.rss import collect_rss_text
from news_bycodex.collectors.web import collect_web_html
from news_bycodex.config import load_keywords, load_sources
from news_bycodex.io import write_jsonl, write_source_error
from news_bycodex.models import RawItem, ReportData, SourceConfig
from news_bycodex.render import render_report


FIXTURE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><item><title>Fixture agent launch</title>
<link>https://example.com/agent</link><description>Released AI agent framework for autonomous coding agent workflows</description>
</item></channel></rss>"""

FIXTURE_WEB = """
<html><body><a href="/agent">Fixture agentic framework launch</a></body></html>
"""


def fixture_raw_item(source: SourceConfig) -> RawItem:
    return RawItem(
        source_id=source.id,
        source_name=source.name,
        source_type=source.type,
        title="Fixture agent launch",
        url="https://example.com/agent",
        summary="Released AI agent framework for autonomous coding agent workflows",
        metadata={"collector": f"fixture_{source.type}"},
    )


def collect_fixture_source(source: SourceConfig, keywords: list[str]) -> list[RawItem]:
    if source.type == "rss":
        return collect_rss_text(source, FIXTURE_RSS, keywords)
    if source.type == "web":
        return collect_web_html(source, FIXTURE_WEB, keywords)

    item = fixture_raw_item(source)
    if keywords and not text_matches_keywords(f"{item.title} {item.summary}", keywords):
        return []
    return [item]


def collect_source(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
    offline_fixtures: bool,
) -> list[RawItem]:
    if offline_fixtures:
        return collect_fixture_source(source, keywords)
    if source.type == "rss":
        response = client.get(str(source.url), timeout=20)
        response.raise_for_status()
        return collect_rss_text(source, response.text, keywords)
    if source.type == "web":
        response = client.get(str(source.url), timeout=20)
        response.raise_for_status()
        return collect_web_html(source, response.text, keywords)
    if source.type == "hn_algolia":
        return collect_hn_algolia(client, source, keywords)
    if source.type == "arxiv":
        return collect_arxiv(client, source, keywords)
    if source.type == "github_search":
        return collect_github_search(client, source, keywords)
    if source.type == "reddit_json":
        return collect_reddit_json(client, source, keywords)
    return []


def executive_summary(top_count: int, weak_count: int, error_count: int) -> str:
    return (
        f"Collected and structured {top_count} high-signal trends and "
        f"{weak_count} weak signals. Recorded {error_count} source collection errors."
    )


def duplicate_related_items(item: RawItem, raw_items: list[RawItem]) -> list[str]:
    duplicate_key = canonical_url(item.url)
    duplicates = [raw_item for raw_item in raw_items if canonical_url(raw_item.url) == duplicate_key]
    if len(duplicates) <= 1:
        return []
    return [
        f"{duplicate.source_name}: {duplicate.url}"
        for duplicate in duplicates
    ]


def normalize_trend(item: RawItem, raw_items: list[RawItem], credibility: float, history_text: str):
    trend = normalize_item(item, source_credibility=credibility, history_text=history_text)
    return trend.model_copy(update={"related_items": duplicate_related_items(item, raw_items)})


def run_report(args: Namespace) -> Path:
    sources = [source for source in load_sources(args.sources) if source.enabled]
    keywords = load_keywords(args.keywords)
    raw_dir = Path("data/raw") / args.date
    processed_dir = Path("data/processed") / args.date
    error_path = raw_dir / "errors.jsonl"
    raw_items: list[RawItem] = []
    source_errors: list[dict[str, str]] = []

    with httpx.Client(headers={"User-Agent": "news-bycodex/0.1"}) as client:
        for source in sources:
            try:
                items = collect_source(client, source, keywords, args.offline_fixtures)
                capped_items = items[: args.limit_per_source]
                raw_items.extend(capped_items)
                write_jsonl(raw_dir / f"{source.id}.jsonl", capped_items)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                source_errors.append({"source_id": source.id, "message": message})
                write_source_error(error_path, source.id, message)

    deduped = dedupe_raw_items(raw_items)
    credibility = {source.id: source.credibility for source in sources}
    history_path = Path("memory/trend_history.md")
    history_text = history_path.read_text(encoding="utf-8") if history_path.exists() else ""
    trends = [
        normalize_trend(
            item,
            raw_items=raw_items,
            credibility=credibility.get(item.source_id, 0.5),
            history_text=history_text,
        )
        for item in deduped
    ]
    trends.sort(key=lambda item: item.signal_strength, reverse=True)
    top_trends = [item for item in trends if item.signal_strength >= 3]
    weak_signals = [item for item in trends if item.signal_strength < 3]
    report = ReportData(
        date=args.date,
        generated_at=datetime.now(timezone.utc),
        executive_summary=executive_summary(len(top_trends), len(weak_signals), len(source_errors)),
        top_trends=top_trends,
        weak_signals=weak_signals,
        deferred_items=[],
        source_errors=source_errors,
    )
    write_jsonl(processed_dir / "trends.jsonl", trends)
    return render_report(report, args.output_dir)
