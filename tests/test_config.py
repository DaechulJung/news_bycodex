from pathlib import Path

from news_bycodex.config import load_keywords, load_sources


def test_load_sources_and_keywords(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    keyword_file = tmp_path / "keywords.yaml"
    source_file.write_text(
        """
sources:
  - id: hacker_news
    name: Hacker News Search
    type: hn_algolia
    enabled: true
    url: https://hn.algolia.com/api/v1/search_by_date
    credibility: 0.8
    limit: 5
""",
        encoding="utf-8",
    )
    keyword_file.write_text(
        """
keywords:
  - LLM Agent
  - autonomous coding agent
""",
        encoding="utf-8",
    )

    sources = load_sources(source_file)
    keywords = load_keywords(keyword_file)

    assert sources[0].id == "hacker_news"
    assert sources[0].type == "hn_algolia"
    assert sources[0].credibility == 0.8
    assert keywords == ["LLM Agent", "autonomous coding agent"]
