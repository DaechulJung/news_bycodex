from pathlib import Path

import httpx

from news_bycodex.collectors.api import (
    collect_arxiv,
    collect_github_search,
    collect_hn_algolia,
    collect_reddit_json,
)
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


def test_collect_rss_text_ignores_malformed_dates():
    source = SourceConfig(
        id="hf",
        name="Hugging Face",
        type="rss",
        url="https://huggingface.co/blog/feed.xml",
        limit=5,
    )
    xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title>Agent update</title>
          <link>https://example.com/agent-update</link>
          <description>Agent details</description>
          <pubDate>not a date</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = collect_rss_text(source, xml, ["agent"])

    assert len(items) == 1
    assert items[0].published_at is None


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


def test_collect_web_html_skips_links_without_href():
    source = SourceConfig(
        id="geeknews",
        name="GeekNews",
        type="web",
        url="https://news.hada.io/",
        limit=5,
        selectors={"item": "a", "title": "a"},
    )
    html = """
    <html>
      <body>
        <a>Codex without href</a>
        <a href="">Codex empty href</a>
        <a href="/codex">Codex valid href</a>
      </body>
    </html>
    """

    items = collect_web_html(source, html, ["codex"])

    assert len(items) == 1
    assert items[0].url == "https://news.hada.io/codex"


def test_collect_hn_algolia_maps_hits():
    source = SourceConfig(
        id="hn",
        name="Hacker News",
        type="hn_algolia",
        url="https://hn.algolia.com/api/v1/search_by_date",
        limit=2,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "agent"
        assert request.url.params["tags"] == "story"
        assert request.url.params["hitsPerPage"] == "2"
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "title": "Agent launch",
                        "url": "https://example.com/agent",
                        "created_at": "2026-05-03T00:00:00Z",
                        "story_text": "Launch notes",
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_hn_algolia(client, source, ["agent"])

    assert len(items) == 1
    assert items[0].title == "Agent launch"
    assert items[0].published_at is not None
    assert items[0].metadata == {"collector": "hn_algolia", "keyword": "agent"}


def test_collect_arxiv_maps_atom_entries():
    source = SourceConfig(
        id="arxiv",
        name="arXiv",
        type="arxiv",
        url="https://export.arxiv.org/api/query",
        limit=3,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search_query"] == 'all:"agent" OR all:"codex"'
        return httpx.Response(
            200,
            text="""
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title> Agent
                  Systems </title>
                <id>https://arxiv.org/abs/2605.00001</id>
                <summary> A
                  paper </summary>
                <published>2026-05-03T00:00:00Z</published>
              </entry>
            </feed>
            """,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_arxiv(client, source, ["agent", "codex"])

    assert len(items) == 1
    assert items[0].title == "Agent Systems"
    assert items[0].summary == "A paper"
    assert items[0].published_at is not None


def test_collect_github_search_queries_keywords_and_deduplicates_urls():
    source = SourceConfig(
        id="github",
        name="GitHub",
        type="github_search",
        url="https://api.github.com/search/repositories",
        limit=3,
    )
    seen_queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        seen_queries.append(query)
        assert request.url.params["sort"] == "updated"
        assert request.url.params["order"] == "desc"
        assert request.url.params["per_page"] == "3"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": f"example/{query}",
                        "html_url": "https://github.com/example/shared",
                        "description": f"{query} repo",
                        "updated_at": "2026-05-03T01:00:00Z",
                        "stargazers_count": 10,
                    },
                    {
                        "full_name": f"example/{query}-unique",
                        "html_url": f"https://github.com/example/{query}",
                        "description": "",
                        "pushed_at": "2026-05-02T01:00:00Z",
                        "stargazers_count": 5,
                    },
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_github_search(client, source, ["agent", "codex"])

    assert seen_queries == ["agent", "codex"]
    assert [item.url for item in items] == [
        "https://github.com/example/shared",
        "https://github.com/example/agent",
        "https://github.com/example/codex",
    ]
    assert items[0].published_at is not None


def test_collect_reddit_json_filters_keywords_and_skips_incomplete_entries():
    source = SourceConfig(
        id="reddit",
        name="Reddit",
        type="reddit_json",
        url="https://www.reddit.com/r/LocalLLaMA/new.json",
        limit=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "news-bycodex/0.1"
        assert request.url.params["limit"] == "5"
        return httpx.Response(
            200,
            json={
                "data": {
                    "children": [
                        {"data": {"title": "", "permalink": "/r/test/comments/1", "selftext": "agent"}},
                        {"data": {"title": "Agent without permalink", "selftext": ""}},
                        {
                            "data": {
                                "title": "Agent discussion",
                                "permalink": "/r/test/comments/2",
                                "selftext": "Codex notes",
                                "score": 7,
                            }
                        },
                        {
                            "data": {
                                "title": "Database discussion",
                                "permalink": "/r/test/comments/3",
                                "selftext": "",
                            }
                        },
                    ]
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_reddit_json(client, source, ["agent"])

    assert len(items) == 1
    assert items[0].title == "Agent discussion"
    assert items[0].url == "https://www.reddit.com/r/test/comments/2"
    assert items[0].metadata == {"collector": "reddit_json", "score": 7}
