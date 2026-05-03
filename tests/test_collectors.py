from pathlib import Path

import httpx

from news_bycodex.collectors.rss import collect_rss_text
from news_bycodex.collectors.web import collect_web_html
from news_bycodex.models import SourceConfig


def test_collect_rss_text_filters_keywords():
    source = SourceConfig(
        id="hf",
        name="Hugging Face",
        type="rss",
        url="https://huggingface.co/blog/feed.xml",
        limit=5,
    )
    xml = Path("tests/fixtures/rss.xml").read_text(encoding="utf-8")

    items = collect_rss_text(source, xml, ["agent"])

    assert len(items) == 1
    assert items[0].title == "New agent framework"
    assert items[0].source_id == "hf"


def test_collect_web_html_extracts_links():
    source = SourceConfig(
        id="geeknews",
        name="GeekNews",
        type="web",
        url="https://news.hada.io/",
        limit=2,
        selectors={"item": "a", "title": "a"},
    )
    html = Path("tests/fixtures/web.html").read_text(encoding="utf-8")

    items = collect_web_html(source, html, ["codex"])

    assert len(items) == 1
    assert items[0].title == "Codex harness patterns"
    assert items[0].url == "https://example.com/codex"
