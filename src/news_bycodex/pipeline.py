from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from news_bycodex.analysis import (
    canonical_url,
    dedupe_raw_items,
    group_similar_trends,
    normalize_item,
    sort_trends_by_hotness,
)
from news_bycodex.agents.codex_runner import run_codex_agent_workflow
from news_bycodex.collectors.api import (
    collect_arxiv,
    collect_github_search,
    collect_google_search,
    collect_hn_algolia,
    collect_reddit_json,
)
from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.collectors.rss import collect_rss_text
from news_bycodex.collectors.web import collect_web_html
from news_bycodex.collectors.youtube import collect_youtube_source, is_youtube_source
from news_bycodex.config import load_keywords, load_sources
from news_bycodex.io import write_jsonl, write_source_error
from news_bycodex.models import RawItem, ReportData, SourceConfig, TrendItem
from news_bycodex.render import render_report
from news_bycodex.review import final_review_report
from news_bycodex.storage import SeenItemStore


FIXTURE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><item><title>Fixture agent launch</title>
<link>https://example.com/agent</link><description>Released AI agent framework for autonomous coding agent workflows</description>
</item></channel></rss>"""

FIXTURE_WEB = """
<html><body><a href="/agent">Fixture agentic framework launch</a></body></html>
"""
CORE_HOTNESS_THRESHOLD = 45


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
        if is_youtube_source(source):
            return collect_youtube_source(client, source, keywords)
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
    if source.type == "google_search":
        return collect_google_search(client, source, keywords)
    if source.type == "reddit_json":
        return collect_reddit_json(client, source, keywords)
    return []


def collect_source_with_retries(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
    offline_fixtures: bool,
    attempts: int = 2,
) -> list[RawItem]:
    for attempt in range(attempts):
        try:
            return collect_source(client, source, keywords, offline_fixtures)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == attempts - 1:
                raise
    return []


def executive_summary(top_count: int, weak_count: int, error_count: int) -> str:
    parts = [f"핵심 트렌드 {top_count}건", f"관찰 신호 {weak_count}건"]
    if error_count:
        parts.append(f"수집 이슈 {error_count}건")
    return " · ".join(parts) + "을 정리했습니다."


def deterministic_timestamp(date_value: str) -> datetime:
    return datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc)


def run_timestamp(args: Namespace) -> datetime:
    if args.offline_fixtures:
        return deterministic_timestamp(args.date)
    return datetime.now(timezone.utc)


def with_collected_at(items: list[RawItem], collected_at: datetime) -> list[RawItem]:
    return [item.model_copy(update={"collected_at": collected_at}) for item in items]


def report_window(date_value: str, days: int = 7) -> tuple[datetime, datetime]:
    report_start = datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc)
    return report_start - timedelta(days=days), report_start + timedelta(days=1)


def comparable_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_recent_item(item: RawItem, date_value: str, days: int = 7) -> bool:
    window_start, window_end = report_window(date_value, days)
    event_time = comparable_time(item.published_at or item.collected_at)
    return window_start <= event_time < window_end


def filter_recent_items(items: list[RawItem], date_value: str, days: int = 7) -> list[RawItem]:
    return [item for item in items if is_recent_item(item, date_value, days)]


def duplicate_related_items(item: RawItem, raw_items: list[RawItem]) -> list[str]:
    duplicate_key = canonical_url(item.url)
    duplicates = [raw_item for raw_item in raw_items if canonical_url(raw_item.url) == duplicate_key]
    if len(duplicates) <= 1:
        return []
    related_items = []
    duplicate_count = item.metadata.get("duplicate_count")
    duplicate_sources = item.metadata.get("duplicate_sources")
    if duplicate_count is not None:
        related_items.append(f"duplicate_count={duplicate_count}")
    if duplicate_sources:
        sources = ", ".join(str(source) for source in duplicate_sources)
        related_items.append(f"duplicate_sources={sources}")
    related_items.extend(f"{duplicate.source_name}: {duplicate.url}" for duplicate in duplicates)
    return related_items


def source_context_related_items(item: RawItem) -> list[str]:
    related_items = []
    discussion_url = item.metadata.get("discussion_url")
    if isinstance(discussion_url, str) and discussion_url.startswith(("http://", "https://")):
        if item.source_type == "hn_algolia":
            related_items.append(f"Hacker News discussion: {discussion_url}")
        else:
            related_items.append(f"{item.source_name}: {discussion_url}")
    return related_items


def unique_related_items(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def normalize_trend(item: RawItem, raw_items: list[RawItem], credibility: float, history_text: str):
    trend = normalize_item(item, source_credibility=credibility, history_text=history_text)
    related_items = unique_related_items(
        duplicate_related_items(item, raw_items) + source_context_related_items(item)
    )
    return trend.model_copy(update={"related_items": related_items})


def is_core_trend(item: TrendItem) -> bool:
    return item.signal_strength >= 4 or item.hotness_score >= CORE_HOTNESS_THRESHOLD


def run_report(args: Namespace) -> Path:
    sources = [source for source in load_sources(args.sources) if source.enabled]
    keywords = load_keywords(args.keywords)
    raw_dir = Path("data/raw") / args.date
    processed_dir = Path("data/processed") / args.date
    error_path = raw_dir / "errors.jsonl"
    raw_items: list[RawItem] = []
    source_errors: list[dict[str, str]] = []
    generated_at = run_timestamp(args)
    use_seen_db = getattr(args, "use_seen_db", False)
    seen_store = SeenItemStore() if use_seen_db else None
    if seen_store:
        seen_store.bootstrap_from_processed(exclude_date=args.date)

    write_jsonl(error_path, [])
    with httpx.Client(
        headers={"User-Agent": "news-bycodex/0.1"},
        follow_redirects=True,
        timeout=30,
    ) as client:
        for source in sources:
            source_output = raw_dir / f"{source.id}.jsonl"
            try:
                items = collect_source_with_retries(client, source, keywords, args.offline_fixtures)
                if args.offline_fixtures:
                    items = with_collected_at(items, generated_at)
                items = filter_recent_items(items, args.date)
                if seen_store:
                    items = seen_store.filter_unseen(items)
                capped_items = items[: args.limit_per_source]
                raw_items.extend(capped_items)
                write_jsonl(source_output, capped_items)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                source_errors.append({"source_id": source.id, "message": message})
                write_jsonl(source_output, [])
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
    trends = sort_trends_by_hotness(group_similar_trends(trends))
    top_trends = [item for item in trends if is_core_trend(item)]
    weak_signals = [item for item in trends if not is_core_trend(item)]
    report = ReportData(
        date=args.date,
        generated_at=generated_at,
        executive_summary=executive_summary(len(top_trends), len(weak_signals), len(source_errors)),
        top_trends=top_trends,
        weak_signals=weak_signals,
        deferred_items=[],
        source_errors=source_errors,
    )
    report, editorial_reviews = final_review_report(report)
    codex_audit: list[dict[str, object]] = []
    codex_agent_mode = getattr(args, "codex_agents", "off")
    if codex_agent_mode != "off":
        report, codex_audit = run_codex_agent_workflow(
            report,
            raw_items,
            processed_dir,
            codex_agent_mode,
        )
        editorial_reviews = report.editorial_reviews
    trends = report.top_trends + report.weak_signals + report.deferred_items
    write_jsonl(processed_dir / "trends.jsonl", trends)
    write_jsonl(processed_dir / "editorial_review.jsonl", editorial_reviews)
    write_jsonl(processed_dir / "codex_agent_audit.jsonl", codex_audit)
    output = render_report(report, args.output_dir)
    if seen_store:
        seen_store.mark_seen(raw_items)
    return output
