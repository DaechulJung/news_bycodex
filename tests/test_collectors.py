from datetime import datetime, timezone
from pathlib import Path

import httpx

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
from news_bycodex.collectors.youtube import collect_youtube_source
from news_bycodex.models import SourceConfig


def test_text_matches_keywords_uses_boundaries_for_short_acronyms():
    assert text_matches_keywords("New AI agent workflow", ["AI"]) is True
    assert text_matches_keywords("Sazerac - Antoine's Cocktail", ["AI"]) is False


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


def test_collect_rss_text_extracts_media_thumbnail_image():
    source = SourceConfig(
        id="youtube",
        name="YouTube",
        type="rss",
        url="https://example.com/feed.xml",
    )
    xml = """<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <entry>
    <title>Agent framework video</title>
    <link href="https://www.youtube.com/watch?v=example"/>
    <media:thumbnail url="https://i.ytimg.com/vi/example/hqdefault.jpg"/>
  </entry>
</feed>"""

    items = collect_rss_text(source, xml, ["agent"])

    assert items[0].metadata["image_url"] == "https://i.ytimg.com/vi/example/hqdefault.jpg"


def test_collect_youtube_source_uses_browser_headers_and_parses_rss():
    source = SourceConfig(
        id="youtube_jocoding",
        name="JoCoding YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCQNE2JmbasNYbjGAcuBiRRg",
        limit=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("Mozilla/5.0")
        return httpx.Response(
            200,
            text="""<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <entry>
    <title>Codex agent workflow update</title>
    <link href="https://www.youtube.com/watch?v=abc123agent"/>
    <media:thumbnail url="https://i.ytimg.com/vi/abc123agent/hqdefault.jpg"/>
    <published>2026-05-08T00:00:00+00:00</published>
  </entry>
</feed>""",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["codex"])

    assert len(items) == 1
    assert items[0].title == "Codex agent workflow update"
    assert items[0].metadata["collector"] == "youtube_rss"
    assert items[0].metadata["image_url"] == "https://i.ytimg.com/vi/abc123agent/hqdefault.jpg"


def test_collect_youtube_source_falls_back_to_channel_page_after_rss_404():
    source = SourceConfig(
        id="youtube_jocoding",
        name="JoCoding YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCQNE2JmbasNYbjGAcuBiRRg",
        limit=5,
        selectors={"channel_url": "https://www.youtube.com/@jocoding/videos"},
    )
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == "/feeds/videos.xml":
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            text="""
            <html><body>
              <a id="video-title" href="/watch?v=abc123agent" title="Codex goal 기능 정리">
                Codex goal 기능 정리
              </a>
            </body></html>
            """,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["codex"])

    assert requested_urls == [
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCQNE2JmbasNYbjGAcuBiRRg",
        "https://www.youtube.com/@jocoding/videos",
    ]
    assert len(items) == 1
    assert items[0].url == "https://www.youtube.com/watch?v=abc123agent"
    assert items[0].metadata["collector"] == "youtube_channel_page"
    assert items[0].metadata["fallback_reason"] == "rss_http_404"
    assert items[0].metadata["image_url"] == "https://i.ytimg.com/vi/abc123agent/hqdefault.jpg"


def test_collect_youtube_source_discovers_replacement_rss_from_channel_page():
    source = SourceConfig(
        id="youtube_code_factory",
        name="Code Factory YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCOLDCHANNEL1",
        limit=5,
        selectors={"channel_url": "https://www.youtube.com/@codefactory_official/videos"},
    )
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if str(request.url) == str(source.url):
            return httpx.Response(404, request=request)
        if str(request.url) == "https://www.youtube.com/@codefactory_official/videos":
            return httpx.Response(
                200,
                text="""
                <html><head>
                  <link rel="alternate" type="application/rss+xml"
                    href="https://www.youtube.com/feeds/videos.xml?channel_id=UCREALCHANNEL">
                </head></html>
                """,
            )
        return httpx.Response(
            200,
            text="""<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Cursor Codex multi-agent workflow</title>
    <link href="https://www.youtube.com/watch?v=abc123agent"/>
    <published>2026-05-08T00:00:00+00:00</published>
  </entry>
</feed>""",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["codex"])

    assert requested_urls == [
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCOLDCHANNEL1",
        "https://www.youtube.com/@codefactory_official/videos",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCREALCHANNEL",
    ]
    assert len(items) == 1
    assert items[0].title == "Cursor Codex multi-agent workflow"
    assert items[0].metadata["collector"] == "youtube_rss_fallback"
    assert items[0].metadata["fallback_reason"] == "rss_http_404"


def test_collect_youtube_source_returns_empty_when_reachable_fallback_has_no_keyword_match():
    source = SourceConfig(
        id="youtube_jocoding",
        name="JoCoding YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCQNE2JmbasNYbjGAcuBiRRg",
        limit=5,
        selectors={"channel_url": "https://www.youtube.com/@jocoding/videos"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feeds/videos.xml":
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            text="""
            <html><body>
              <a id="video-title" href="/watch?v=abc123agent" title="평범한 개발 브이로그">
                평범한 개발 브이로그
              </a>
            </body></html>
            """,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["codex"])

    assert items == []


def test_collect_youtube_source_skips_fallback_links_without_titles():
    source = SourceConfig(
        id="youtube_gymcoding",
        name="GymCoding YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCZ30aWiMw5C8mGcESlAGQbA",
        limit=5,
        selectors={"channel_url": "https://www.youtube.com/@gymcoding/videos"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feeds/videos.xml":
            return httpx.Response(404, request=request)
        return httpx.Response(200, text='<a href="/watch?v=abc123agent"></a>')

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["agent"])

    assert items == []


def test_collect_youtube_source_parses_lockup_view_model_titles():
    source = SourceConfig(
        id="youtube_code_factory",
        name="Code Factory YouTube",
        type="rss",
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCOLDCHANNEL1",
        limit=5,
        selectors={"channel_url": "https://www.youtube.com/@codefactory_official/videos"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/feeds/videos.xml":
            return httpx.Response(404, request=request)
        return httpx.Response(
            200,
            text="""
            <script>
            var ytInitialData = {
              "contents": {
                "richItemRenderer": {
                  "content": {
                    "lockupViewModel": {
                      "contentId": "abc123agent",
                      "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                      "metadata": {
                        "lockupMetadataViewModel": {
                          "title": {"content": "Cursor Codex multi-agent workflow"},
                          "metadata": {
                            "contentMetadataViewModel": {
                              "metadataRows": [{
                                "metadataParts": [{"text": {"content": "3일 전"}}]
                              }]
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            };
            </script>
            """,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_youtube_source(client, source, ["codex"])

    assert len(items) == 1
    assert items[0].title == "Cursor Codex multi-agent workflow"
    assert items[0].url == "https://www.youtube.com/watch?v=abc123agent"
    assert items[0].published_at is not None
    assert items[0].published_at < datetime.now(timezone.utc)


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


def test_collect_web_html_extracts_visible_month_date_from_listing_text():
    source = SourceConfig(
        id="anthropic_news",
        name="Anthropic News",
        type="web",
        url="https://www.anthropic.com/news",
        limit=5,
        selectors={"item": "a[href^='/news/']"},
    )
    html = """
    <html>
      <body>
        <a href="/news/claude-agent-sdk">
          Product Apr 17, 2026 Claude Agent SDK adds subagent orchestration
        </a>
      </body>
    </html>
    """

    items = collect_web_html(source, html, ["agent"])

    assert len(items) == 1
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026
    assert items[0].published_at.month == 4
    assert items[0].published_at.day == 17


def test_collect_web_html_extracts_iso_date_from_listing_text():
    source = SourceConfig(
        id="llamaindex_blog",
        name="LlamaIndex Blog",
        type="web",
        url="https://www.llamaindex.ai/blog",
        limit=5,
        selectors={"item": ".Post", "title": "a[href^='/blog/']"},
    )
    html = """
    <html>
      <body>
        <div class="Post">
          <a href="/blog/newsletter">LlamaIndex Newsletter 2026-04-14</a>
          <p>Agentic document workflow updates.</p>
        </div>
      </body>
    </html>
    """

    items = collect_web_html(source, html, ["agentic"])

    assert len(items) == 1
    assert items[0].published_at is not None
    assert items[0].published_at.year == 2026
    assert items[0].published_at.month == 4
    assert items[0].published_at.day == 14


def test_collect_web_html_deduplicates_links_before_limit():
    source = SourceConfig(
        id="llamaindex_blog",
        name="LlamaIndex Blog",
        type="web",
        url="https://www.llamaindex.ai/blog",
        limit=2,
        selectors={"item": "a[href^='/blog/']"},
    )
    html = """
    <html>
      <body>
        <a href="/blog/parsebench">Introducing ParseBench for AI Agents</a>
        <a href="/blog/parsebench">Introducing ParseBench for AI Agents</a>
        <a href="/blog/llamaparse-mcp">LlamaParse MCP for document agents</a>
      </body>
    </html>
    """

    items = collect_web_html(source, html, ["agent"])

    assert [item.url for item in items] == [
        "https://www.llamaindex.ai/blog/parsebench",
        "https://www.llamaindex.ai/blog/llamaparse-mcp",
    ]


def test_collect_web_html_uses_nested_title_and_card_summary_for_keyword_filtering():
    source = SourceConfig(
        id="llamaindex_blog",
        name="LlamaIndex Blog",
        type="web",
        url="https://www.llamaindex.ai/blog",
        limit=5,
        selectors={"item": ".Post", "title": "a[href^='/blog/']"},
    )
    html = """
    <html>
      <body>
        <div class="Post">
          <a href="/blog/parsebench">Introducing ParseBench</a>
          <p>Document parsing benchmark for production AI agents and eval harnesses.</p>
        </div>
      </body>
    </html>
    """

    items = collect_web_html(source, html, ["agent"])

    assert len(items) == 1
    assert items[0].title == "Introducing ParseBench"
    assert items[0].summary == "Document parsing benchmark for production AI agents and eval harnesses."


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
                        "objectID": "12345",
                        "points": 42,
                        "num_comments": 7,
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
    assert items[0].metadata == {
        "collector": "hn_algolia",
        "keyword": "agent",
        "discussion_url": "https://news.ycombinator.com/item?id=12345",
        "points": 42,
        "comments": 7,
    }


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


def test_collect_google_search_uses_custom_search_api_credentials_and_keywords(monkeypatch):
    source = SourceConfig(
        id="google_search",
        name="Google Search",
        type="google_search",
        url="https://www.googleapis.com/customsearch/v1",
        limit=3,
    )
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    seen_queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_queries.append(request.url.params["q"])
        assert request.url.params["key"] == "test-key"
        assert request.url.params["cx"] == "test-cx"
        assert request.url.params["num"] == "3"
        assert request.url.params["dateRestrict"] == "d7"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "title": "GPT 5.5 model launch analysis",
                        "link": "https://example.com/gpt-55",
                        "snippet": "OpenAI GPT 5.5 agent workflow coverage",
                        "pagemap": {
                            "metatags": [
                                {
                                    "og:image": "https://example.com/gpt-55.jpg",
                                    "article:published_time": "2026-05-04T00:00:00Z",
                                }
                            ]
                        },
                    },
                    {
                        "title": "Duplicate GPT 5.5 result",
                        "link": "https://example.com/gpt-55?utm_source=google",
                        "snippet": "duplicate",
                    },
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_google_search(client, source, ["GPT 5.5", "Codex"])

    assert seen_queries == ["GPT 5.5", "Codex"]
    assert len(items) == 1
    assert items[0].title == "GPT 5.5 model launch analysis"
    assert items[0].summary == "OpenAI GPT 5.5 agent workflow coverage"
    assert items[0].metadata["collector"] == "google_search"
    assert items[0].metadata["keyword"] == "GPT 5.5"
    assert items[0].metadata["image_url"] == "https://example.com/gpt-55.jpg"
    assert items[0].published_at is not None


def test_collect_google_search_falls_back_to_google_news_rss_without_credentials(monkeypatch):
    source = SourceConfig(
        id="google_search",
        name="Google Search",
        type="google_search",
        url="https://www.googleapis.com/customsearch/v1",
        limit=2,
    )
    monkeypatch.delenv("GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SEARCH_ENGINE_ID", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "news.google.com"
        assert request.url.params["q"] == "agent when:7d"
        return httpx.Response(
            200,
            text="""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel>
              <item>
                <title>Agent harness release - Example News</title>
                <link>https://news.google.com/rss/articles/example</link>
                <pubDate>Mon, 04 May 2026 00:00:00 GMT</pubDate>
                <description>Agent harness release coverage</description>
              </item>
            </channel></rss>""",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_google_search(client, source, ["agent"])

    assert len(items) == 1
    assert items[0].title == "Agent harness release - Example News"
    assert items[0].metadata == {
        "collector": "google_news_rss_search",
        "keyword": "agent",
        "fallback_reason": "missing_custom_search_credentials",
    }


def test_collect_google_search_falls_back_when_custom_search_is_closed(monkeypatch):
    source = SourceConfig(
        id="google_search",
        name="Google Search",
        type="google_search",
        url="https://www.googleapis.com/customsearch/v1",
        limit=2,
    )
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "secret-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "www.googleapis.com":
            return httpx.Response(
                403,
                json={
                    "error": {
                        "message": "This project does not have the access to Custom Search JSON API."
                    }
                },
            )
        return httpx.Response(
            200,
            text="""<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel>
              <item>
                <title>Codex goal feature - Example News</title>
                <link>https://news.google.com/rss/articles/codex-goal</link>
                <pubDate>Mon, 04 May 2026 00:00:00 GMT</pubDate>
                <description>Codex goal feature coverage</description>
              </item>
            </channel></rss>""",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items = collect_google_search(client, source, ["Codex"])

    assert requested_hosts == ["www.googleapis.com", "news.google.com"]
    assert items[0].metadata["collector"] == "google_news_rss_search"
    assert items[0].metadata["fallback_reason"] == "custom_search_json_api_unavailable"


def test_collect_google_search_redacts_api_key_from_http_errors(monkeypatch):
    source = SourceConfig(
        id="google_search",
        name="Google Search",
        type="google_search",
        url="https://www.googleapis.com/customsearch/v1",
    )
    monkeypatch.setenv("GOOGLE_SEARCH_API_KEY", "secret-key")
    monkeypatch.setenv("GOOGLE_SEARCH_ENGINE_ID", "test-cx")

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403))) as client:
        try:
            collect_google_search(client, source, ["agent"])
        except RuntimeError as exc:
            message = str(exc)
            assert "secret-key" not in message
            assert "key=REDACTED" in message
            assert "403" in message
        else:
            raise AssertionError("Google HTTP errors should be sanitized")


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
