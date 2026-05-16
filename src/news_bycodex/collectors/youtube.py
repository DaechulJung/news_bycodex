import html
import json
import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from news_bycodex.collectors.base import text_matches_keywords
from news_bycodex.collectors.rss import collect_rss_text
from news_bycodex.models import RawItem, SourceConfig


YOUTUBE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 news-bycodex/0.1"
    ),
    "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}
VIDEO_ID_RE = re.compile(r"(?:watch\?v=|/shorts/)(?P<video_id>[A-Za-z0-9_-]{11})")
JSON_VIDEO_RE = re.compile(
    r'"videoId":"(?P<video_id>[A-Za-z0-9_-]{11})".{0,1600}?'
    r'"title":\{"runs":\[\{"text":"(?P<title>(?:\\.|[^"])*)"\}\]',
    re.DOTALL,
)
YoutubeVideo = tuple[str, str, datetime | None]


def is_youtube_source(source: SourceConfig) -> bool:
    if source.type != "rss" or source.url is None:
        return False
    host = urlparse(str(source.url)).netloc.lower()
    return "youtube.com" in host or source.id.startswith("youtube_")


def collect_youtube_source(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
) -> list[RawItem]:
    if source.url is None:
        return []

    rss_error: httpx.HTTPStatusError | httpx.TransportError | httpx.TimeoutException | None = None
    try:
        response = client.get(str(source.url), headers=YOUTUBE_HEADERS, timeout=20)
        response.raise_for_status()
        return mark_youtube_rss_items(collect_rss_text(source, response.text, keywords))
    except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
        rss_error = exc

    fallback_items, reached_fallback = collect_youtube_fallbacks(client, source, keywords, rss_error)
    if fallback_items or reached_fallback:
        return fallback_items[: source.limit]
    if rss_error:
        raise rss_error
    return []


def mark_youtube_rss_items(
    items: list[RawItem],
    collector: str = "youtube_rss",
    extra_metadata: dict[str, str] | None = None,
) -> list[RawItem]:
    updated: list[RawItem] = []
    for item in items:
        metadata = dict(item.metadata)
        metadata["collector"] = collector
        if extra_metadata:
            metadata.update(extra_metadata)
        updated.append(item.model_copy(update={"metadata": metadata}))
    return updated


def collect_youtube_fallbacks(
    client: httpx.Client,
    source: SourceConfig,
    keywords: list[str],
    rss_error: Exception | None,
) -> tuple[list[RawItem], bool]:
    reason = fallback_reason(rss_error)
    reached_fallback = False
    for fallback_url in fallback_urls(source):
        try:
            response = client.get(fallback_url, headers=YOUTUBE_HEADERS, timeout=20)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException):
            continue
        reached_fallback = True
        rss_items = collect_discovered_rss_feeds(
            client,
            source,
            response.text,
            keywords,
            reason,
        )
        if rss_items:
            return rss_items, reached_fallback
        items = parse_youtube_channel_page(source, response.text, fallback_url, keywords, reason)
        if items:
            return items, reached_fallback
    return [], reached_fallback


def collect_discovered_rss_feeds(
    client: httpx.Client,
    source: SourceConfig,
    html_text: str,
    keywords: list[str],
    reason: str,
) -> list[RawItem]:
    for rss_url in discovered_rss_urls(html_text):
        try:
            response = client.get(rss_url, headers=YOUTUBE_HEADERS, timeout=20)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException):
            continue
        items = collect_rss_text(source, response.text, keywords)
        if items:
            return mark_youtube_rss_items(
                items,
                collector="youtube_rss_fallback",
                extra_metadata={"fallback_reason": reason},
            )
    return []


def discovered_rss_urls(html_text: str) -> list[str]:
    normalized = html.unescape(html_text.replace("\\u0026", "&"))
    soup = BeautifulSoup(normalized, "html.parser")
    urls: list[str] = []
    for link in soup.find_all("link", href=True):
        href = str(link["href"])
        link_type = str(link.get("type", "")).lower()
        if "application/rss+xml" in link_type or "feeds/videos.xml" in href:
            urls.append(href)
    urls.extend(re.findall(r"https://www\.youtube\.com/feeds/videos\.xml\?channel_id=[A-Za-z0-9_-]+", normalized))
    for channel_id in re.findall(r'"channelId"\s*:\s*"(?P<channel_id>[A-Za-z0-9_-]{6,})"', normalized):
        urls.append(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    return list(dict.fromkeys(urls))


def fallback_reason(error: Exception | None) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"rss_http_{error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "rss_timeout"
    if isinstance(error, httpx.TransportError):
        return "rss_transport_error"
    return "rss_unavailable"


def fallback_urls(source: SourceConfig) -> list[str]:
    urls: list[str] = []
    configured = source.selectors.get("channel_url")
    if configured:
        urls.append(configured)
    if source.url is not None:
        channel_id = channel_id_from_feed_url(str(source.url))
        if channel_id:
            urls.append(f"https://www.youtube.com/channel/{channel_id}/videos")
    return list(dict.fromkeys(urls))


def channel_id_from_feed_url(url: str) -> str:
    values = parse_qs(urlparse(url).query).get("channel_id") or []
    return values[0] if values else ""


def parse_youtube_channel_page(
    source: SourceConfig,
    html_text: str,
    page_url: str,
    keywords: Iterable[str],
    reason: str,
) -> list[RawItem]:
    items: list[RawItem] = []
    seen: set[str] = set()
    for video_id, title, published_at in html_anchor_videos(html_text):
        maybe_add_youtube_item(
            items, seen, source, video_id, title, keywords, reason, published_at
        )
    for video_id, title, published_at in json_videos(html_text):
        maybe_add_youtube_item(
            items, seen, source, video_id, title, keywords, reason, published_at
        )
    for video_id, title, published_at in plain_link_videos(html_text, page_url):
        maybe_add_youtube_item(
            items, seen, source, video_id, title, keywords, reason, published_at
        )
    return items[: source.limit]


def html_anchor_videos(html_text: str) -> list[YoutubeVideo]:
    soup = BeautifulSoup(html_text, "html.parser")
    videos: list[YoutubeVideo] = []
    for anchor in soup.find_all("a", href=True):
        video_id = video_id_from_url(str(anchor["href"]))
        if not video_id:
            continue
        title = (
            str(anchor.get("title") or anchor.get("aria-label") or anchor.get_text(" ", strip=True))
            .strip()
        )
        videos.append((video_id, title, None))
    return videos


def json_videos(html_text: str) -> list[YoutubeVideo]:
    videos: list[YoutubeVideo] = []
    videos.extend(yt_initial_data_videos(html_text))
    for match in JSON_VIDEO_RE.finditer(html_text):
        videos.append(
            (
                match.group("video_id"),
                decode_json_string(match.group("title")),
                None,
            )
        )
    return videos


def yt_initial_data_videos(html_text: str) -> list[YoutubeVideo]:
    data = extract_yt_initial_data(html_text)
    if not data:
        return []
    videos: list[YoutubeVideo] = []
    collect_json_video_entries(data, videos)
    return videos


def extract_yt_initial_data(html_text: str) -> object | None:
    for marker in ["var ytInitialData = ", "window[\"ytInitialData\"] = "]:
        start = html_text.find(marker)
        if start == -1:
            continue
        raw = html_text[start + len(marker) :].lstrip()
        try:
            return json.JSONDecoder().raw_decode(raw)[0]
        except json.JSONDecodeError:
            continue
    return None


def collect_json_video_entries(value: object, videos: list[YoutubeVideo]) -> None:
    if isinstance(value, dict):
        lockup = value.get("lockupViewModel")
        if isinstance(lockup, dict):
            video = lockup_video(lockup)
            if video:
                videos.append(video)
        renderer = value.get("videoRenderer")
        if isinstance(renderer, dict):
            video = renderer_video(renderer)
            if video:
                videos.append(video)
        for child in value.values():
            collect_json_video_entries(child, videos)
    elif isinstance(value, list):
        for child in value:
            collect_json_video_entries(child, videos)


def lockup_video(lockup: dict[str, object]) -> YoutubeVideo | None:
    video_id = str(lockup.get("contentId") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None
    content_type = str(lockup.get("contentType") or "")
    if content_type and content_type != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None
    metadata = lockup.get("metadata")
    title = ""
    published_at = None
    if isinstance(metadata, dict):
        lockup_metadata = metadata.get("lockupMetadataViewModel")
        if isinstance(lockup_metadata, dict):
            title = content_text(lockup_metadata.get("title"))
            published_at = first_relative_published_at(lockup_metadata)
    return (video_id, title, published_at) if title else None


def renderer_video(renderer: dict[str, object]) -> YoutubeVideo | None:
    video_id = str(renderer.get("videoId") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None
    title = content_text(renderer.get("title"))
    published_at = first_relative_published_at(renderer.get("publishedTimeText"))
    return (video_id, title, published_at) if title else None


def content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    simple_text = value.get("simpleText")
    if isinstance(simple_text, str):
        return simple_text
    content = value.get("content")
    if isinstance(content, str):
        return content
    runs = value.get("runs")
    if isinstance(runs, list):
        return "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict))
    return ""


def plain_link_videos(html_text: str, page_url: str) -> list[YoutubeVideo]:
    videos: list[YoutubeVideo] = []
    for match in VIDEO_ID_RE.finditer(html_text):
        video_id = match.group("video_id")
        title = title_near_match(html_text, match.start())
        if title:
            videos.append((video_id, title, None))
    return videos


def title_near_match(html_text: str, start: int) -> str:
    window = html_text[max(0, start - 800) : start + 800]
    for pattern in [
        r'title=["\'](?P<title>[^"\']+)["\']',
        r'"title"\s*:\s*"(?P<title>(?:\\.|[^"])*)"',
        r'"text"\s*:\s*"(?P<title>(?:\\.|[^"])*)"',
    ]:
        match = re.search(pattern, window)
        if match:
            return clean_title(decode_json_string(match.group("title")))
    return ""


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    query_video = parse_qs(parsed.query).get("v") or []
    if query_video and re.fullmatch(r"[A-Za-z0-9_-]{11}", query_video[0]):
        return query_video[0]
    match = VIDEO_ID_RE.search(url)
    return match.group("video_id") if match else ""


def maybe_add_youtube_item(
    items: list[RawItem],
    seen: set[str],
    source: SourceConfig,
    video_id: str,
    title: str,
    keywords: Iterable[str],
    reason: str,
    published_at: datetime | None,
) -> None:
    title = clean_title(title)
    if not video_id or video_id in seen or not title:
        return
    if keywords and not text_matches_keywords(title, keywords):
        return
    seen.add(video_id)
    items.append(
        RawItem(
            source_id=source.id,
            source_name=source.name,
            source_type=source.type,
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            published_at=published_at,
            summary=f"{source.name}에서 수집한 YouTube 동영상입니다.",
            metadata={
                "collector": "youtube_channel_page",
                "fallback_reason": reason,
                "image_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            },
        )
    )


def clean_title(value: str) -> str:
    return " ".join(html.unescape(value).split())


def decode_json_string(value: str) -> str:
    try:
        return str(json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return value


def first_relative_published_at(value: object) -> datetime | None:
    if isinstance(value, str):
        return parse_relative_published_at(value)
    if isinstance(value, dict):
        for key in ("content", "simpleText", "text"):
            parsed = first_relative_published_at(value.get(key))
            if parsed:
                return parsed
        runs = value.get("runs")
        if isinstance(runs, list):
            parsed = parse_relative_published_at(
                "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict))
            )
            if parsed:
                return parsed
        for child in value.values():
            parsed = first_relative_published_at(child)
            if parsed:
                return parsed
    elif isinstance(value, list):
        for child in value:
            parsed = first_relative_published_at(child)
            if parsed:
                return parsed
    return None


def parse_relative_published_at(value: str) -> datetime | None:
    normalized = clean_title(value).lower()
    korean = re.search(r"(?P<count>\d+)\s*(?P<unit>초|분|시간|일|주|개월|달|년)\s*전", normalized)
    if korean:
        return datetime.now(timezone.utc) - relative_delta(
            int(korean.group("count")),
            korean.group("unit"),
        )
    english = re.search(
        r"(?P<count>\d+)\s*(?P<unit>second|minute|hour|day|week|month|year)s?\s+ago",
        normalized,
    )
    if english:
        return datetime.now(timezone.utc) - relative_delta(
            int(english.group("count")),
            english.group("unit"),
        )
    return None


def relative_delta(count: int, unit: str) -> timedelta:
    if unit in {"초", "second"}:
        return timedelta(seconds=count)
    if unit in {"분", "minute"}:
        return timedelta(minutes=count)
    if unit in {"시간", "hour"}:
        return timedelta(hours=count)
    if unit in {"일", "day"}:
        return timedelta(days=count)
    if unit in {"주", "week"}:
        return timedelta(weeks=count)
    if unit in {"개월", "달", "month"}:
        return timedelta(days=30 * count)
    if unit in {"년", "year"}:
        return timedelta(days=365 * count)
    return timedelta()
