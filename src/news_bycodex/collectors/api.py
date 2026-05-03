import xml.etree.ElementTree as ET

import httpx

from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.models import RawItem, SourceConfig


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
                results.append(
                    RawItem(
                        source_id=source.id,
                        source_name=source.name,
                        source_type=source.type,
                        title=title,
                        url=url,
                        published_at=hit.get("created_at"),
                        summary=hit.get("story_text") or "",
                        metadata={"collector": "hn_algolia", "keyword": keyword},
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
