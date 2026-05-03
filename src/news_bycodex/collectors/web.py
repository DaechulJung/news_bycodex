from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.models import RawItem, SourceConfig


def collect_web_html(source: SourceConfig, html: str, keywords: list[str]) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    item_selector = source.selectors.get("item", "a")
    nodes = soup.select(item_selector)
    items: list[RawItem] = []
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
        url = urljoin(base_url, str(href or ""))
        if not title or not url:
            continue
        if keywords and not text_matches_keywords(title, keywords):
            continue
        items.append(
            RawItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title=title,
                url=url,
                summary="",
                metadata={"collector": "web"},
            )
        )
    return items[: source.limit]
