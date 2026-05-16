from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from dateutil.parser import ParserError
import re

from news_bycodex.analysis import canonical_url
from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.models import RawItem, SourceConfig


VISIBLE_DATE_RE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def collect_web_html(source: SourceConfig, html: str, keywords: list[str]) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    item_selector = source.selectors.get("item", "a")
    nodes = soup.select(item_selector)
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    base_url = str(source.url) if source.url else ""
    for node in nodes:
        title_node = (
            node.select_one(source.selectors.get("title", ""))
            if source.selectors.get("title")
            else node
        )
        title = title_node.get_text(" ", strip=True) if title_node else node.get_text(" ", strip=True)
        href = node.get("href") if hasattr(node, "get") else None
        if not href and title_node is not None:
            href = title_node.get("href")
        href_text = str(href or "").strip()
        if not href_text:
            continue
        url = urljoin(base_url, href_text)
        if not title or not url:
            continue
        summary = summary_from_listing_node(node, title, title_node)
        if keywords and not text_matches_keywords(f"{title} {summary}", keywords):
            continue
        url_key = canonical_url(url)
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        items.append(
            RawItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title=title,
                url=url,
                published_at=published_at_from_visible_text(f"{title} {summary}"),
                summary=summary,
                metadata={"collector": "web"},
            )
        )
    return items[: source.limit]


def summary_from_listing_node(node, title: str, title_node) -> str:
    if title_node is None or title_node is node:
        return ""
    text = " ".join(node.get_text(" ", strip=True).split())
    if text.startswith(title):
        text = text[len(title) :].strip()
    return text


def published_at_from_visible_text(text: str):
    match = VISIBLE_DATE_RE.search(text) or ISO_DATE_RE.search(text)
    if not match:
        return None
    try:
        return date_parser.parse(match.group(0))
    except (ParserError, TypeError, OverflowError):
        return None
