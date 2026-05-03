from pathlib import Path

import pytest
from pydantic import ValidationError

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


def test_load_sources_requires_sources_key(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="sources must be a list"):
        load_sources(source_file)


def test_load_sources_requires_sources_list(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text("sources: hacker_news", encoding="utf-8")

    with pytest.raises(ValueError, match="sources must be a list"):
        load_sources(source_file)


def test_load_sources_requires_mapping_entries(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text(
        """
sources:
  - hacker_news
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sources\\[0\\] must be a mapping"):
        load_sources(source_file)


def test_load_sources_does_not_drop_empty_entries(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text(
        """
sources:
  - null
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sources\\[0\\] must be a mapping"):
        load_sources(source_file)


def test_load_sources_rejects_unknown_source_fields(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text(
        """
sources:
  - id: hacker_news
    name: Hacker News Search
    type: hn_algolia
    enabled: true
    url: https://hn.algolia.com/api/v1/search_by_date
    credibilty: 0.8
    limit: 5
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        load_sources(source_file)


def test_load_sources_requires_url_for_enabled_sources(tmp_path: Path):
    source_file = tmp_path / "sources.yaml"
    source_file.write_text(
        """
sources:
  - id: hacker_news
    name: Hacker News Search
    type: hn_algolia
    enabled: true
    credibility: 0.8
    limit: 5
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="enabled sources require url"):
        load_sources(source_file)


def test_load_keywords_requires_keyword_list(tmp_path: Path):
    keyword_file = tmp_path / "keywords.yaml"
    keyword_file.write_text("keywords: LLM Agent", encoding="utf-8")

    with pytest.raises(ValueError, match="keywords must be a list"):
        load_keywords(keyword_file)


def test_committed_configs_load_successfully():
    assert load_sources(Path("configs/sources.yaml"))
    assert load_keywords(Path("configs/keywords.yaml"))
