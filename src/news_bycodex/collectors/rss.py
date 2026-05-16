import feedparser
from dateutil.parser import ParserError
from dateutil import parser as date_parser

from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.models import RawItem, SourceConfig


def collect_rss_text(source: SourceConfig, xml: str, keywords: list[str]) -> list[RawItem]:
    feed = feedparser.parse(xml)
    items: list[RawItem] = []
    for entry in feed.entries:
        title = str(entry.get("title", "")).strip()
        summary = str(entry.get("summary", "")).strip()
        url = str(entry.get("link") or entry.get("id") or "").strip()
        if not title or not url:
            continue
        if keywords and not text_matches_keywords(f"{title} {summary}", keywords):
            continue
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
                summary=summary,
                metadata=rss_metadata(entry),
            )
        )
    return items[: source.limit]


def rss_metadata(entry) -> dict[str, str]:
    metadata = {"collector": "rss"}
    image_url = rss_image_url(entry)
    if image_url:
        metadata["image_url"] = image_url
    return metadata


def rss_image_url(entry) -> str:
    thumbnails = entry.get("media_thumbnail") or []
    if thumbnails:
        thumbnail_url = thumbnails[0].get("url")
        if thumbnail_url:
            return str(thumbnail_url)
    media_content = entry.get("media_content") or []
    for content in media_content:
        content_url = content.get("url")
        medium = content.get("medium", "")
        content_type = content.get("type", "")
        if content_url and (medium == "image" or str(content_type).startswith("image/")):
            return str(content_url)
    return ""
