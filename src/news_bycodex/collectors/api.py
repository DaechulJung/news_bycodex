import os
import re
import xml.etree.ElementTree as ET

from dateutil import parser as date_parser
from dateutil.parser import ParserError
import feedparser
import httpx

from news_bycodex.analysis import canonical_url
from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.models import RawItem, SourceConfig


GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"
GOOGLE_CUSTOM_SEARCH_CLOSED_MESSAGE = (
    "This project does not have the access to Custom Search JSON API"
)


def collect_hn_algolia(
    client: httpx.Client, source: SourceConfig, keywords: list[str]
) -> list[RawItem]:
    results: list[RawItem] = []
    for keyword in keywords:
        response = client.get(
            str(source.url),
            params={"query": keyword, "tags": "story", "hitsPerPage": source.limit},
        )
        response.raise_for_status()
        for hit in response.json().get("hits", []):
            title = hit.get("title") or hit.get("story_title") or ""
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            if title and url:
                metadata = {"collector": "hn_algolia", "keyword": keyword}
                object_id = hit.get("objectID")
                if object_id:
                    metadata["discussion_url"] = f"https://news.ycombinator.com/item?id={object_id}"
                if hit.get("points") is not None:
                    metadata["points"] = hit.get("points")
                if hit.get("num_comments") is not None:
                    metadata["comments"] = hit.get("num_comments")
                results.append(
                    RawItem(
                        source_id=source.id,
                        source_name=source.name,
                        source_type=source.type,
                        title=title,
                        url=url,
                        published_at=hit.get("created_at"),
                        summary=hit.get("story_text") or "",
                        metadata=metadata,
                    )
                )
    return results[: source.limit]


def collect_arxiv(client: httpx.Client, source: SourceConfig, keywords: list[str]) -> list[RawItem]:
    query = " OR ".join(f'all:"{keyword}"' for keyword in keywords[:5])
    response = client.get(
        str(source.url), params={"search_query": query, "start": 0, "max_results": source.limit}
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[RawItem] = []
    for entry in root.findall("atom:entry", namespace):
        title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
        url = (entry.findtext("atom:id", default="", namespaces=namespace) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=namespace) or "").strip()
        published = entry.findtext("atom:published", default=None, namespaces=namespace)
        if title and url:
            items.append(
                RawItem(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type,
                    title=" ".join(title.split()),
                    url=url,
                    published_at=published,
                    summary=" ".join(summary.split()),
                    metadata={"collector": "arxiv"},
                )
            )
    return items[: source.limit]


def collect_github_search(
    client: httpx.Client, source: SourceConfig, keywords: list[str]
) -> list[RawItem]:
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    for keyword in keywords:
        response = client.get(
            str(source.url),
            params={"q": keyword, "sort": "updated", "order": "desc", "per_page": source.limit},
        )
        response.raise_for_status()
        for repo in response.json().get("items", []):
            title = repo.get("full_name", "")
            url = repo.get("html_url", "")
            summary = repo.get("description") or ""
            if not title or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(
                RawItem(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type,
                    title=title,
                    url=url,
                    published_at=repo.get("updated_at") or repo.get("pushed_at") or repo.get("created_at"),
                    summary=summary,
                    metadata={
                        "collector": "github_search",
                        "stars": repo.get("stargazers_count", 0),
                    },
                )
            )
            if len(items) >= source.limit:
                return items
    return items[: source.limit]


def collect_google_search(
    client: httpx.Client, source: SourceConfig, keywords: list[str]
) -> list[RawItem]:
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
    engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "").strip()
    fallback_reason = ""
    if api_key and engine_id:
        try:
            return collect_google_custom_search(client, source, keywords, api_key, engine_id)
        except GoogleCustomSearchUnavailable:
            fallback_reason = "custom_search_json_api_unavailable"
    else:
        fallback_reason = "missing_custom_search_credentials"

    return collect_google_news_rss_search(client, source, keywords, fallback_reason)


def collect_google_custom_search(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
    api_key: str,
    engine_id: str,
) -> list[RawItem]:
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    for keyword in keywords:
        response = client.get(
            str(source.url),
            params={
                "key": api_key,
                "cx": engine_id,
                "q": keyword,
                "num": min(source.limit, 10),
                "dateRestrict": "d7",
            },
        )
        raise_google_search_for_status(response)
        for result in response.json().get("items", []):
            title = result.get("title", "")
            url = result.get("link", "")
            if not title or not url:
                continue
            key = canonical_url(url)
            if key in seen_urls:
                continue
            seen_urls.add(key)
            metadata = {
                "collector": "google_search",
                "keyword": keyword,
                "display_link": result.get("displayLink", ""),
            }
            published_at, image_url = google_result_metadata(result)
            if image_url:
                metadata["image_url"] = image_url
            items.append(
                RawItem(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type,
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=result.get("snippet") or "",
                    metadata=metadata,
                )
            )
            if len(items) >= source.limit:
                return items
    return items[: source.limit]


def collect_google_news_rss_search(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
    fallback_reason: str,
) -> list[RawItem]:
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    for keyword in keywords:
        response = client.get(
            GOOGLE_NEWS_RSS_SEARCH_URL,
            params={
                "q": f"{keyword} when:7d",
                "hl": "ko",
                "gl": "KR",
                "ceid": "KR:ko",
            },
            timeout=20,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue
            key = canonical_url(url)
            if key in seen_urls:
                continue
            seen_urls.add(key)
            published = entry.get("published") or entry.get("updated")
            try:
                published_at = date_parser.parse(published) if published else None
            except (ParserError, TypeError, OverflowError):
                published_at = None
            items.append(
                RawItem(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type,
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=entry.get("summary", ""),
                    metadata={
                        "collector": "google_news_rss_search",
                        "keyword": keyword,
                        "fallback_reason": fallback_reason,
                    },
                )
            )
            if len(items) >= source.limit:
                return items
    return items[: source.limit]


class GoogleCustomSearchUnavailable(RuntimeError):
    pass


def raise_google_search_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    url = redact_google_api_key(str(response.request.url))
    body = redact_google_api_key(response.text)[:300]
    message = (
        f"Google Search HTTP {response.status_code} {response.reason_phrase} "
        f"for url '{url}': {body}"
    )
    if GOOGLE_CUSTOM_SEARCH_CLOSED_MESSAGE in response.text:
        raise GoogleCustomSearchUnavailable(message)
    raise RuntimeError(message)


def redact_google_api_key(value: str) -> str:
    redacted = re.sub(r"([?&]key=)[^&\s]+", r"\1REDACTED", value)
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
    if api_key:
        redacted = redacted.replace(api_key, "REDACTED")
    return redacted


def google_result_metadata(result: dict) -> tuple[str | None, str | None]:
    for metatag in result.get("pagemap", {}).get("metatags", []):
        published_at = (
            metatag.get("article:published_time")
            or metatag.get("og:updated_time")
            or metatag.get("date")
        )
        image_url = metatag.get("og:image") or metatag.get("twitter:image")
        if published_at or image_url:
            return published_at, image_url
    return None, None


def collect_reddit_json(
    client: httpx.Client, source: SourceConfig, keywords: list[str]
) -> list[RawItem]:
    response = client.get(
        str(source.url),
        params={"limit": source.limit},
        headers={"User-Agent": "news-bycodex/0.1"},
    )
    response.raise_for_status()
    items: list[RawItem] = []
    for child in response.json().get("data", {}).get("children", []):
        data = child.get("data", {})
        title = data.get("title", "")
        summary = data.get("selftext", "")
        permalink = data.get("permalink", "")
        if not title or not permalink:
            continue
        if keywords and not text_matches_keywords(f"{title} {summary}", keywords):
            continue
        items.append(
            RawItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title=title,
                url=f"https://www.reddit.com{permalink}",
                summary=summary,
                metadata={"collector": "reddit_json", "score": data.get("score", 0)},
            )
        )
    return items[: source.limit]
