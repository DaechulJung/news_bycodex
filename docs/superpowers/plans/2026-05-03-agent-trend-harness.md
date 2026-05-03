# Agent Trend Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Codex-native local MVP that collects real Agent/AI trend signals and renders `reports/YYYY-MM-DD.html`.

**Architecture:** Codex coordinates the editorial workflow through `AGENTS.md`, role prompts, memory files, and repo-local skills. Python helpers perform deterministic work: source loading, collection, raw snapshot storage, normalization, scoring, and HTML rendering. The first slice runs locally and leaves stable skill/plugin/MCP boundaries visible for future extraction.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, `httpx`, `feedparser`, `beautifulsoup4`, `jinja2`, `pydantic`, `PyYAML`, `python-dateutil`.

---

## File Structure

- Create `pyproject.toml`: package metadata, CLI entrypoint, runtime and test dependencies.
- Create `.gitignore`: ignores caches, virtualenvs, generated data, and reports.
- Create `src/news_bycodex/models.py`: shared Pydantic models for sources, raw items, normalized items, scores, and reports.
- Create `src/news_bycodex/config.py`: YAML loaders for `configs/sources.yaml` and `configs/keywords.yaml`.
- Create `src/news_bycodex/io.py`: JSONL, raw snapshot, processed record, and error-writing helpers.
- Create `src/news_bycodex/collectors/`: RSS, public API, and HTML source collectors.
- Create `src/news_bycodex/analysis.py`: normalization, deduplication, categorization, and scoring.
- Create `src/news_bycodex/render.py`: Jinja2 report rendering.
- Create `src/news_bycodex/pipeline.py`: end-to-end run orchestration.
- Create `src/news_bycodex/cli.py`: local command entrypoint.
- Create `src/news_bycodex/templates/report.html.j2`: standalone HTML report template.
- Create `configs/sources.yaml` and `configs/keywords.yaml`: initial real source and keyword configuration.
- Create `memory/*.md`: editorial memory files.
- Create `prompts/roles/*.md`: Codex subagent role prompts.
- Create `skills/*/SKILL.md`: repo-local skill instructions for collection, analysis, and publishing.
- Create `tests/`: fixture-driven tests for config, collectors, analysis, rendering, and pipeline behavior.

## Preflight: Initialize Repository Metadata

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Confirm Git state**

Run: `git status --short`

Expected in the current workspace: FAIL with `fatal: not a git repository`.

- [ ] **Step 2: Initialize Git**

Run: `git init`

Expected: output includes `Initialized empty Git repository`.

- [ ] **Step 3: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
data/raw/
data/processed/
reports/*.html
*.log
.env
```

- [ ] **Step 4: Commit baseline docs**

```powershell
git add AGENTS.md docs .gitignore
git commit -m "docs: add agent trend harness design"
```

Expected: commit succeeds with tracked `AGENTS.md`, spec, plan, and `.gitignore`.

## Task 1: Python Package and CLI Contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/news_bycodex/__init__.py`
- Create: `src/news_bycodex/cli.py`
- Test: `tests/test_cli_contract.py`

- [ ] **Step 1: Write the failing CLI contract test**

```python
from news_bycodex.cli import build_parser


def test_cli_accepts_date_and_limit_arguments():
    parser = build_parser()
    args = parser.parse_args([
        "report",
        "--date",
        "2026-05-03",
        "--limit-per-source",
        "3",
    ])

    assert args.command == "report"
    assert args.date == "2026-05-03"
    assert args.limit_per_source == 3
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run python -m pytest tests/test_cli_contract.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'news_bycodex'`.

- [ ] **Step 3: Create package metadata**

```toml
[project]
name = "news-bycodex"
version = "0.1.0"
description = "Codex-native daily Agent/AI trend intelligence harness"
requires-python = ">=3.11"
dependencies = [
  "beautifulsoup4>=4.12.0",
  "feedparser>=6.0.11",
  "httpx>=0.27.0",
  "jinja2>=3.1.0",
  "pydantic>=2.7.0",
  "python-dateutil>=2.9.0",
  "PyYAML>=6.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "respx>=0.21.0",
  "ruff>=0.5.0",
]

[project.scripts]
news-bycodex = "news_bycodex.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 4: Create the CLI parser**

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="news-bycodex")
    subcommands = parser.add_subparsers(dest="command", required=True)

    report = subcommands.add_parser("report", help="Generate a daily Agent/AI trend report")
    report.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format")
    report.add_argument("--limit-per-source", type=int, default=10)
    report.add_argument("--sources", default="configs/sources.yaml")
    report.add_argument("--keywords", default="configs/keywords.yaml")
    report.add_argument("--output-dir", default="reports")
    report.add_argument("--offline-fixtures", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "report":
        from news_bycodex.pipeline import run_report

        run_report(args)
        return 0
    return 1
```

Create `src/news_bycodex/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 5: Run the test and verify it passes**

Run: `uv run python -m pytest tests/test_cli_contract.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml src tests
git commit -m "feat: add package and CLI contract"
```

## Task 2: Source Config and Shared Models

**Files:**
- Create: `src/news_bycodex/models.py`
- Create: `src/news_bycodex/config.py`
- Create: `configs/sources.yaml`
- Create: `configs/keywords.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config test**

```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run python -m pytest tests/test_config.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing `load_sources`.

- [ ] **Step 3: Create shared models**

```python
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


SourceType = Literal["rss", "hn_algolia", "arxiv", "github_search", "reddit_json", "web"]
Category = Literal[
    "model",
    "agent_framework",
    "coding_agent",
    "research",
    "product",
    "tooling",
    "benchmark",
    "company",
    "other",
]
Maturity = Literal["rumor", "prototype", "beta", "released", "adopted"]
Impact = Literal["low", "medium", "high", "strategic"]


class SourceConfig(BaseModel):
    id: str
    name: str
    type: SourceType
    enabled: bool = True
    url: HttpUrl | None = None
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=100)
    selectors: dict[str, str] = Field(default_factory=dict)


class RawItem(BaseModel):
    source_id: str
    source_name: str
    source_type: SourceType
    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    summary: str
    category: Category
    maturity: Maturity
    impact: Impact
    signal_strength: int = Field(ge=1, le=5)
    why_it_matters: str
    related_items: list[str] = Field(default_factory=list)


class ReportData(BaseModel):
    date: str
    generated_at: datetime
    executive_summary: str
    top_trends: list[TrendItem]
    weak_signals: list[TrendItem]
    deferred_items: list[TrendItem]
    source_errors: list[dict[str, str]] = Field(default_factory=list)
```

- [ ] **Step 4: Create config loaders**

```python
from pathlib import Path
from typing import Any

import yaml

from news_bycodex.models import SourceConfig


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def load_sources(path: str | Path) -> list[SourceConfig]:
    data = _load_yaml(Path(path))
    return [SourceConfig.model_validate(item) for item in data.get("sources", []) if item]


def load_keywords(path: str | Path) -> list[str]:
    data = _load_yaml(Path(path))
    keywords = data.get("keywords", [])
    if not isinstance(keywords, list):
        raise ValueError("keywords must be a list")
    return [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
```

- [ ] **Step 5: Create initial source and keyword configs**

`configs/keywords.yaml`:

```yaml
keywords:
  - LLM Agent
  - agentic framework
  - deep agent
  - autonomous coding agent
  - AI agent framework
  - LLM Model
  - Claude Code
  - Codex
  - OpenAI agent
  - Hugging Face agent
```

`configs/sources.yaml`:

```yaml
sources:
  - id: hacker_news
    name: Hacker News Algolia
    type: hn_algolia
    enabled: true
    url: https://hn.algolia.com/api/v1/search_by_date
    credibility: 0.8
    limit: 10
  - id: arxiv
    name: arXiv Search
    type: arxiv
    enabled: true
    url: https://export.arxiv.org/api/query
    credibility: 0.9
    limit: 10
  - id: github_search
    name: GitHub Repository Search
    type: github_search
    enabled: true
    url: https://api.github.com/search/repositories
    credibility: 0.75
    limit: 10
  - id: reddit_machine_learning
    name: Reddit MachineLearning
    type: reddit_json
    enabled: true
    url: https://www.reddit.com/r/MachineLearning/new.json
    credibility: 0.65
    limit: 10
  - id: huggingface_blog
    name: Hugging Face Blog
    type: rss
    enabled: true
    url: https://huggingface.co/blog/feed.xml
    credibility: 0.85
    limit: 10
  - id: geeknews
    name: GeekNews
    type: web
    enabled: true
    url: https://news.hada.io/
    credibility: 0.7
    limit: 10
    selectors:
      item: "a"
      title: "a"
  - id: papers_with_code
    name: Papers with Code Latest
    type: web
    enabled: true
    url: https://paperswithcode.com/latest
    credibility: 0.8
    limit: 10
    selectors:
      item: "a"
      title: "a"
```

- [ ] **Step 6: Run tests and commit**

Run: `uv run python -m pytest tests/test_config.py -q`

Expected: PASS.

```powershell
git add configs src/news_bycodex/models.py src/news_bycodex/config.py tests/test_config.py
git commit -m "feat: add source config and trend models"
```

## Task 3: Raw Storage and Error Recording

**Files:**
- Create: `src/news_bycodex/io.py`
- Test: `tests/test_io.py`

- [ ] **Step 1: Write the failing IO test**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from news_bycodex.io import write_jsonl, write_source_error
from news_bycodex.models import RawItem


def test_write_jsonl_and_source_error(tmp_path: Path):
    item = RawItem(
        source_id="hacker_news",
        source_name="Hacker News",
        source_type="hn_algolia",
        title="New coding agent",
        url="https://example.com/agent",
        published_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
    )

    output = tmp_path / "items.jsonl"
    write_jsonl(output, [item])
    write_source_error(tmp_path / "errors.jsonl", "reddit", "HTTP 429")

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    errors = [json.loads(line) for line in (tmp_path / "errors.jsonl").read_text(encoding="utf-8").splitlines()]

    assert rows[0]["title"] == "New coding agent"
    assert errors[0]["source_id"] == "reddit"
    assert errors[0]["message"] == "HTTP 429"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run python -m pytest tests/test_io.py -q`

Expected: FAIL with missing `news_bycodex.io`.

- [ ] **Step 3: Create IO helpers**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_jsonable(item: BaseModel | dict) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump(mode="json")
    return item


def write_jsonl(path: str | Path, items: Iterable[BaseModel | dict]) -> None:
    output = Path(path)
    ensure_dir(output.parent)
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(to_jsonable(item), ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, item: BaseModel | dict) -> None:
    output = Path(path)
    ensure_dir(output.parent)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_jsonable(item), ensure_ascii=False) + "\n")


def write_source_error(path: str | Path, source_id: str, message: str) -> None:
    append_jsonl(
        path,
        {
            "source_id": source_id,
            "message": message,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
```

- [ ] **Step 4: Run tests and commit**

Run: `uv run python -m pytest tests/test_io.py tests/test_config.py -q`

Expected: PASS.

```powershell
git add src/news_bycodex/io.py tests/test_io.py
git commit -m "feat: add JSONL storage helpers"
```

## Task 4: Collectors for RSS, Public APIs, and HTML

**Files:**
- Create: `src/news_bycodex/collectors/__init__.py`
- Create: `src/news_bycodex/collectors/base.py`
- Create: `src/news_bycodex/collectors/rss.py`
- Create: `src/news_bycodex/collectors/api.py`
- Create: `src/news_bycodex/collectors/web.py`
- Create: `tests/fixtures/rss.xml`
- Create: `tests/fixtures/web.html`
- Test: `tests/test_collectors.py`

- [ ] **Step 1: Write collector fixture tests**

```python
from pathlib import Path

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
```

- [ ] **Step 2: Add fixtures**

`tests/fixtures/rss.xml`:

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>AI Blog</title>
    <item>
      <title>New agent framework</title>
      <link>https://example.com/agent-framework</link>
      <description>Agent framework release notes</description>
      <pubDate>Sun, 03 May 2026 00:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Unrelated database update</title>
      <link>https://example.com/database</link>
      <description>Storage engine details</description>
    </item>
  </channel>
</rss>
```

`tests/fixtures/web.html`:

```html
<html>
  <body>
    <a href="https://example.com/codex">Codex harness patterns</a>
    <a href="https://example.com/database">Database release notes</a>
  </body>
</html>
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `uv run python -m pytest tests/test_collectors.py -q`

Expected: FAIL with missing collector modules.

- [ ] **Step 4: Implement base helpers**

```python
from collections.abc import Iterable


def text_matches_keywords(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)
```

- [ ] **Step 5: Implement RSS collector**

```python
import feedparser
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
        published_at = date_parser.parse(published) if published else None
        items.append(
            RawItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title=title,
                url=url,
                published_at=published_at,
                summary=summary,
                metadata={"collector": "rss"},
            )
        )
    return items[: source.limit]
```

- [ ] **Step 6: Implement HTML collector**

```python
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
        title_node = node.select_one(source.selectors.get("title", "")) if source.selectors.get("title") else node
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
```

- [ ] **Step 7: Implement HTTP API collectors**

```python
import xml.etree.ElementTree as ET

import httpx

from news_bycodex.models import RawItem, SourceConfig


def collect_hn_algolia(client: httpx.Client, source: SourceConfig, keywords: list[str]) -> list[RawItem]:
    results: list[RawItem] = []
    for keyword in keywords:
        response = client.get(str(source.url), params={"query": keyword, "tags": "story", "hitsPerPage": source.limit})
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
    response = client.get(str(source.url), params={"search_query": query, "start": 0, "max_results": source.limit})
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


def collect_github_search(client: httpx.Client, source: SourceConfig, keywords: list[str]) -> list[RawItem]:
    query = " ".join(keywords[:3])
    response = client.get(str(source.url), params={"q": query, "sort": "updated", "order": "desc", "per_page": source.limit})
    response.raise_for_status()
    items: list[RawItem] = []
    for repo in response.json().get("items", []):
        title = repo.get("full_name", "")
        url = repo.get("html_url", "")
        summary = repo.get("description") or ""
        if title and url:
            items.append(
                RawItem(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type,
                    title=title,
                    url=url,
                    summary=summary,
                    metadata={"collector": "github_search", "stars": repo.get("stargazers_count", 0)},
                )
            )
    return items[: source.limit]


def collect_reddit_json(client: httpx.Client, source: SourceConfig, keywords: list[str]) -> list[RawItem]:
    response = client.get(str(source.url), params={"limit": source.limit}, headers={"User-Agent": "news-bycodex/0.1"})
    response.raise_for_status()
    items: list[RawItem] = []
    for child in response.json().get("data", {}).get("children", []):
        data = child.get("data", {})
        title = data.get("title", "")
        summary = data.get("selftext", "")
        if keywords and not any(keyword.lower() in f"{title} {summary}".lower() for keyword in keywords):
            continue
        permalink = data.get("permalink", "")
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
```

- [ ] **Step 8: Run tests and commit**

Run: `uv run python -m pytest tests/test_collectors.py -q`

Expected: PASS.

```powershell
git add src/news_bycodex/collectors tests/fixtures tests/test_collectors.py
git commit -m "feat: add initial source collectors"
```

## Task 5: Normalization, Deduplication, and Scoring

**Files:**
- Create: `src/news_bycodex/analysis.py`
- Test: `tests/test_analysis.py`

- [ ] **Step 1: Write analysis tests**

```python
from news_bycodex.analysis import dedupe_raw_items, normalize_item
from news_bycodex.models import RawItem


def test_dedupe_raw_items_by_url():
    items = [
        RawItem(source_id="hn", source_name="HN", source_type="hn_algolia", title="Agent SDK", url="https://example.com/a"),
        RawItem(source_id="gh", source_name="GitHub", source_type="github_search", title="Agent SDK", url="https://example.com/a"),
    ]

    deduped = dedupe_raw_items(items)

    assert len(deduped) == 1
    assert deduped[0].source_id == "hn"


def test_normalize_item_scores_coding_agent():
    raw = RawItem(
        source_id="gh",
        source_name="GitHub",
        source_type="github_search",
        title="autonomous coding agent framework",
        url="https://example.com/agent",
        summary="A released coding agent framework for developers",
        metadata={"stars": 250},
    )

    trend = normalize_item(raw, source_credibility=0.8, history_text="")

    assert trend.category == "coding_agent"
    assert trend.maturity == "released"
    assert trend.signal_strength >= 4
    assert "developer" in trend.why_it_matters.lower()
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `uv run python -m pytest tests/test_analysis.py -q`

Expected: FAIL with missing `analysis`.

- [ ] **Step 3: Implement analysis functions**

```python
from collections import OrderedDict

from news_bycodex.models import Impact, Maturity, RawItem, TrendItem


def dedupe_raw_items(items: list[RawItem]) -> list[RawItem]:
    deduped: OrderedDict[str, RawItem] = OrderedDict()
    for item in items:
        key = item.url.rstrip("/").lower()
        if key not in deduped:
            deduped[key] = item
    return list(deduped.values())


def classify_category(text: str) -> str:
    lowered = text.lower()
    if "coding agent" in lowered or "claude code" in lowered or "codex" in lowered:
        return "coding_agent"
    if "agent framework" in lowered or "agentic framework" in lowered:
        return "agent_framework"
    if "benchmark" in lowered or "leaderboard" in lowered:
        return "benchmark"
    if "arxiv" in lowered or "paper" in lowered or "research" in lowered:
        return "research"
    if "model" in lowered or "llm" in lowered:
        return "model"
    if "release" in lowered or "launch" in lowered or "product" in lowered:
        return "product"
    return "other"


def classify_maturity(text: str) -> Maturity:
    lowered = text.lower()
    if "rumor" in lowered or "leak" in lowered:
        return "rumor"
    if "prototype" in lowered or "demo" in lowered:
        return "prototype"
    if "beta" in lowered or "preview" in lowered:
        return "beta"
    if "adopted" in lowered or "production" in lowered:
        return "adopted"
    return "released"


def impact_from_score(score: int) -> Impact:
    if score >= 5:
        return "strategic"
    if score >= 4:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def signal_score(raw: RawItem, source_credibility: float, history_text: str) -> int:
    text = f"{raw.title} {raw.summary}".lower()
    score = 1
    if source_credibility >= 0.8:
        score += 1
    if any(token in text for token in ["agent", "codex", "claude code", "autonomous", "framework"]):
        score += 1
    if any(token in text for token in ["release", "launched", "benchmark", "paper", "github"]):
        score += 1
    if raw.metadata.get("stars", 0) >= 100:
        score += 1
    if raw.title.lower() in history_text.lower():
        score -= 1
    return max(1, min(5, score))


def normalize_item(raw: RawItem, source_credibility: float, history_text: str) -> TrendItem:
    text = f"{raw.title} {raw.summary}"
    score = signal_score(raw, source_credibility, history_text)
    category = classify_category(text)
    return TrendItem(
        title=raw.title,
        url=raw.url,
        source=raw.source_name,
        published_at=raw.published_at,
        summary=raw.summary or raw.title,
        category=category,
        maturity=classify_maturity(text),
        impact=impact_from_score(score),
        signal_strength=score,
        why_it_matters=why_it_matters(category, score),
        related_items=[],
    )


def why_it_matters(category: str, score: int) -> str:
    if category == "coding_agent":
        return "This may affect developer workflows and autonomous software engineering adoption."
    if category == "agent_framework":
        return "This may shape how teams build, evaluate, and operate agentic systems."
    if category == "research":
        return "This may introduce techniques that product teams adopt after validation."
    if score >= 4:
        return "This has strong relevance to near-term Agent/AI strategy."
    return "This is a weak signal worth tracking for follow-up."
```

- [ ] **Step 4: Run tests and commit**

Run: `uv run python -m pytest tests/test_analysis.py -q`

Expected: PASS.

```powershell
git add src/news_bycodex/analysis.py tests/test_analysis.py
git commit -m "feat: add trend normalization and scoring"
```

## Task 6: HTML Report Renderer

**Files:**
- Create: `src/news_bycodex/render.py`
- Create: `src/news_bycodex/templates/report.html.j2`
- Test: `tests/test_render.py`

- [ ] **Step 1: Write renderer test**

```python
from datetime import datetime, timezone
from pathlib import Path

from news_bycodex.models import ReportData, TrendItem
from news_bycodex.render import render_report


def test_render_report_writes_html(tmp_path: Path):
    item = TrendItem(
        title="Codex agent harness",
        url="https://example.com/codex",
        source="Hacker News",
        summary="A harness for agent trend reports",
        category="coding_agent",
        maturity="released",
        impact="high",
        signal_strength=4,
        why_it_matters="This may affect developer workflows.",
    )
    report = ReportData(
        date="2026-05-03",
        generated_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        executive_summary="One strong coding-agent signal.",
        top_trends=[item],
        weak_signals=[],
        deferred_items=[],
        source_errors=[{"source_id": "reddit", "message": "HTTP 429"}],
    )

    output = render_report(report, tmp_path)

    html = output.read_text(encoding="utf-8")
    assert output.name == "2026-05-03.html"
    assert "Codex agent harness" in html
    assert "Source Coverage" in html
    assert "HTTP 429" in html
```

- [ ] **Step 2: Run test and verify it fails**

Run: `uv run python -m pytest tests/test_render.py -q`

Expected: FAIL with missing renderer.

- [ ] **Step 3: Implement renderer**

```python
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from news_bycodex.io import ensure_dir
from news_bycodex.models import ReportData


def render_report(report: ReportData, output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    ensure_dir(directory)
    env = Environment(
        loader=PackageLoader("news_bycodex", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")
    output = directory / f"{report.date}.html"
    output.write_text(template.render(report=report), encoding="utf-8")
    return output
```

- [ ] **Step 4: Create HTML template**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent/AI Trend Report - {{ report.date }}</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; color: #172026; background: #f7f8fa; }
    main { max-width: 1080px; margin: 0 auto; padding: 32px 20px; }
    header { border-bottom: 3px solid #172026; margin-bottom: 24px; }
    h1 { font-size: 32px; margin: 0 0 8px; }
    h2 { font-size: 21px; margin-top: 28px; }
    .summary { font-size: 16px; line-height: 1.55; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
    .card { background: white; border: 1px solid #d9dee3; border-radius: 8px; padding: 16px; }
    .meta { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
    .tag { font-size: 12px; background: #e9eef3; border-radius: 999px; padding: 4px 8px; }
    a { color: #0b5cad; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .error { color: #8a1f11; }
  </style>
</head>
<body>
<main>
  <header>
    <h1>Agent/AI Trend Report</h1>
    <p>{{ report.date }} · generated {{ report.generated_at.isoformat() }}</p>
  </header>

  <section>
    <h2>Executive Summary</h2>
    <p class="summary">{{ report.executive_summary }}</p>
  </section>

  <section>
    <h2>Top Trends</h2>
    <div class="grid">
      {% for item in report.top_trends %}
      <article class="card">
        <h3><a href="{{ item.url }}">{{ item.title }}</a></h3>
        <div class="meta">
          <span class="tag">{{ item.category }}</span>
          <span class="tag">{{ item.maturity }}</span>
          <span class="tag">{{ item.impact }}</span>
          <span class="tag">signal {{ item.signal_strength }}/5</span>
        </div>
        <p>{{ item.summary }}</p>
        <p><strong>Why it matters:</strong> {{ item.why_it_matters }}</p>
        <p><small>{{ item.source }}</small></p>
      </article>
      {% endfor %}
    </div>
  </section>

  <section>
    <h2>Weak Signals</h2>
    {% for item in report.weak_signals %}
    <p><a href="{{ item.url }}">{{ item.title }}</a> · {{ item.source }} · signal {{ item.signal_strength }}/5</p>
    {% else %}
    <p>No weak signals were promoted in this run.</p>
    {% endfor %}
  </section>

  <section>
    <h2>Noise and Deferred Items</h2>
    {% for item in report.deferred_items %}
    <p><a href="{{ item.url }}">{{ item.title }}</a> · {{ item.source }}</p>
    {% else %}
    <p>No deferred items were recorded.</p>
    {% endfor %}
  </section>

  <section>
    <h2>Source Coverage</h2>
    {% for error in report.source_errors %}
    <p class="error">{{ error.source_id }}: {{ error.message }}</p>
    {% else %}
    <p>All configured sources completed without recorded errors.</p>
    {% endfor %}
  </section>
</main>
</body>
</html>
```

- [ ] **Step 5: Run tests and commit**

Run: `uv run python -m pytest tests/test_render.py -q`

Expected: PASS.

```powershell
git add src/news_bycodex/render.py src/news_bycodex/templates tests/test_render.py
git commit -m "feat: add HTML report renderer"
```

## Task 7: End-to-End Pipeline

**Files:**
- Create: `src/news_bycodex/pipeline.py`
- Modify: `src/news_bycodex/cli.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write fixture-mode pipeline test**

```python
from argparse import Namespace
from pathlib import Path

from news_bycodex.pipeline import run_report


def test_run_report_with_offline_fixtures(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    sources.write_text(
        """
sources:
  - id: fixture_rss
    name: Fixture RSS
    type: rss
    enabled: true
    url: https://example.com/rss.xml
    credibility: 0.9
    limit: 5
""",
        encoding="utf-8",
    )
    keywords.write_text("keywords:\n  - agent\n", encoding="utf-8")
    args = Namespace(
        date="2026-05-03",
        limit_per_source=5,
        sources=str(sources),
        keywords=str(keywords),
        output_dir=str(tmp_path / "reports"),
        offline_fixtures=True,
    )

    output = run_report(args)

    assert output.exists()
    assert "Agent/AI Trend Report" in output.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test and verify it fails**

Run: `uv run python -m pytest tests/test_pipeline.py -q`

Expected: FAIL with missing pipeline behavior.

- [ ] **Step 3: Implement pipeline orchestration**

```python
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import httpx

from news_bycodex.analysis import dedupe_raw_items, normalize_item
from news_bycodex.collectors.api import collect_arxiv, collect_github_search, collect_hn_algolia, collect_reddit_json
from news_bycodex.collectors.rss import collect_rss_text
from news_bycodex.collectors.web import collect_web_html
from news_bycodex.config import load_keywords, load_sources
from news_bycodex.io import write_jsonl, write_source_error
from news_bycodex.models import RawItem, ReportData, SourceConfig
from news_bycodex.render import render_report


FIXTURE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><item><title>Fixture agent launch</title>
<link>https://example.com/agent</link><description>Released coding agent framework</description>
</item></channel></rss>"""


def collect_source(client: httpx.Client, source: SourceConfig, keywords: list[str], offline_fixtures: bool) -> list[RawItem]:
    if offline_fixtures and source.type == "rss":
        return collect_rss_text(source, FIXTURE_RSS, keywords)
    if source.type == "rss":
        response = client.get(str(source.url), timeout=20)
        response.raise_for_status()
        return collect_rss_text(source, response.text, keywords)
    if source.type == "web":
        response = client.get(str(source.url), timeout=20)
        response.raise_for_status()
        return collect_web_html(source, response.text, keywords)
    if source.type == "hn_algolia":
        return collect_hn_algolia(client, source, keywords)
    if source.type == "arxiv":
        return collect_arxiv(client, source, keywords)
    if source.type == "github_search":
        return collect_github_search(client, source, keywords)
    if source.type == "reddit_json":
        return collect_reddit_json(client, source, keywords)
    return []


def executive_summary(top_count: int, weak_count: int, error_count: int) -> str:
    return (
        f"Collected and structured {top_count} high-signal trends and "
        f"{weak_count} weak signals. Recorded {error_count} source collection errors."
    )


def run_report(args: Namespace) -> Path:
    sources = [source for source in load_sources(args.sources) if source.enabled]
    keywords = load_keywords(args.keywords)
    raw_dir = Path("data/raw") / args.date
    processed_dir = Path("data/processed") / args.date
    error_path = raw_dir / "errors.jsonl"
    raw_items: list[RawItem] = []
    source_errors: list[dict[str, str]] = []

    with httpx.Client(headers={"User-Agent": "news-bycodex/0.1"}) as client:
        for source in sources:
            try:
                items = collect_source(client, source, keywords, args.offline_fixtures)
                raw_items.extend(items[: args.limit_per_source])
                write_jsonl(raw_dir / f"{source.id}.jsonl", items)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                source_errors.append({"source_id": source.id, "message": message})
                write_source_error(error_path, source.id, message)

    deduped = dedupe_raw_items(raw_items)
    credibility = {source.id: source.credibility for source in sources}
    history_text = Path("memory/trend_history.md").read_text(encoding="utf-8") if Path("memory/trend_history.md").exists() else ""
    trends = [
        normalize_item(item, source_credibility=credibility.get(item.source_id, 0.5), history_text=history_text)
        for item in deduped
    ]
    trends.sort(key=lambda item: item.signal_strength, reverse=True)
    top_trends = [item for item in trends if item.signal_strength >= 3]
    weak_signals = [item for item in trends if item.signal_strength < 3]
    report = ReportData(
        date=args.date,
        generated_at=datetime.now(timezone.utc),
        executive_summary=executive_summary(len(top_trends), len(weak_signals), len(source_errors)),
        top_trends=top_trends,
        weak_signals=weak_signals,
        deferred_items=[],
        source_errors=source_errors,
    )
    write_jsonl(processed_dir / "trends.jsonl", trends)
    return render_report(report, args.output_dir)
```

- [ ] **Step 4: Run pipeline test**

Run: `uv run python -m pytest tests/test_pipeline.py -q`

Expected: PASS.

- [ ] **Step 5: Run CLI in fixture mode**

Run: `uv run news-bycodex report --date 2026-05-03 --offline-fixtures --output-dir reports`

Expected: creates `reports/2026-05-03.html`.

- [ ] **Step 6: Commit**

```powershell
git add src/news_bycodex/pipeline.py src/news_bycodex/cli.py tests/test_pipeline.py
git commit -m "feat: add end-to-end report pipeline"
```

## Task 8: Codex Memory, Role Prompts, and Repo-Local Skills

**Files:**
- Create: `memory/interests.md`
- Create: `memory/noise_patterns.md`
- Create: `memory/trend_history.md`
- Create: `prompts/roles/editor_in_chief.md`
- Create: `prompts/roles/community_reporter.md`
- Create: `prompts/roles/research_reporter.md`
- Create: `prompts/roles/product_reporter.md`
- Create: `prompts/roles/developer_reporter.md`
- Create: `prompts/roles/trend_analyst.md`
- Create: `prompts/roles/html_publisher.md`
- Create: `skills/collect-rss/SKILL.md`
- Create: `skills/collect-web/SKILL.md`
- Create: `skills/collect-search/SKILL.md`
- Create: `skills/analyze-trends/SKILL.md`
- Create: `skills/render-html-report/SKILL.md`

- [ ] **Step 1: Create memory files**

`memory/interests.md`:

```markdown
# Editorial Interests

Prioritize daily signals about AI agents, coding agents, agent frameworks, model releases, evaluation benchmarks, developer tooling, and enterprise adoption.

Track named entities such as ChatGPT, Claude, Codex, Claude Code, Grok, Hugging Face, smolagents, OpenAI agents, Google agent products, Anthropic releases, GitHub repositories, and emerging autonomous coding systems.
```

`memory/noise_patterns.md`:

```markdown
# Noise Patterns

Treat generic AI listicles, recycled launch summaries, SEO-only tool directories, unsourced rumors, and duplicate reposts as low signal.

Promote weak signals only when they have credible source context, unusual developer traction, or clear relevance to agentic workflows.
```

`memory/trend_history.md`:

```markdown
# Trend History

This file records major trends already covered by the harness. Add dated entries after human review so future reports can identify novelty and follow-up signals.
```

- [ ] **Step 2: Create role prompts**

Use this exact pattern for `prompts/roles/editor_in_chief.md`:

```markdown
# Editor-in-Chief

You coordinate the daily Agent/AI trend report. Assign collection work by source group, check source coverage, resolve duplicates, and require the final report to distinguish strong trends from weak signals and noise.
```

Create the remaining role prompts with these role bodies:

```markdown
# Community Reporter

Collect fast-moving discussion signals from GeekNews, Hacker News, Reddit, and similar communities. Prefer items with concrete links, technical detail, or unusual discussion velocity.
```

```markdown
# Research Reporter

Collect arXiv, Papers with Code, benchmark, and research-project signals. Emphasize method novelty, reproducibility, evaluation quality, and connection to agentic systems.
```

```markdown
# Product Reporter

Track official product announcements from OpenAI, Google, Anthropic, Hugging Face, Product Hunt, and comparable product sources. Separate released products from previews, rumors, and marketing-only posts.
```

```markdown
# Developer Reporter

Track GitHub repositories, releases, SDKs, examples, and developer adoption signals. Note stars, forks, release activity, and practical relevance to building agents or coding assistants.
```

```markdown
# Trend Analyst

Normalize collected items into trend records. Classify category, maturity, impact, and signal strength. Explain why each promoted item matters and mark uncertainty clearly.
```

```markdown
# HTML Publisher

Render the final trend intelligence briefing as a standalone HTML file. Prioritize scanning, source links, short summaries, maturity labels, impact labels, and source coverage notes.
```

- [ ] **Step 3: Create repo-local skill files**

Use this structure for `skills/analyze-trends/SKILL.md`:

```markdown
---
name: analyze-trends
description: Structure raw Agent/AI news items into categorized, scored trend intelligence.
---

# Analyze Trends

Input: collected `RawItem` objects in memory during `run_report`, plus `memory/trend_history.md`.

Output: `data/processed/YYYY-MM-DD/trends.jsonl`.

Rules:
- Deduplicate by canonical URL first.
- Classify each item by category, maturity, impact, and signal strength.
- Promote strong signals when `signal_strength >= 3`.
- Mark weak signals separately instead of discarding them.
- Preserve source URLs and source names.
- `data/raw/YYYY-MM-DD/*.jsonl` is the persisted audit/replay artifact for collected raw items.
- Manual or future replay workflows may use `data/raw/YYYY-MM-DD/*.jsonl` as their input source.
- The automated pipeline currently uses `memory/trend_history.md` for novelty checks.
- `memory/interests.md` and `memory/noise_patterns.md` are editorial guidance for Codex/manual review until they are wired into automated scoring.
```

Create the other skill files with matching input/output contracts:

```markdown
---
name: collect-rss
description: Collect Agent/AI trend items from configured RSS or Atom feeds.
---

# Collect RSS

Input: `configs/sources.yaml`, `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/<source_id>.jsonl`.

Rules:
- Prefer official RSS or Atom feeds.
- Filter by configured keywords when a source is broad.
- Keep raw titles, URLs, dates, summaries, and source metadata.
- Record source failures in `data/raw/YYYY-MM-DD/errors.jsonl`.
```

```markdown
---
name: collect-web
description: Collect public Agent/AI trend items from configured HTML sources.
---

# Collect Web

Input: `configs/sources.yaml`, `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/<source_id>.jsonl`.

Rules:
- Use conservative request rates.
- Extract public links and titles only.
- Prefer stable CSS selectors in source config.
- Record blocked or failed sources without failing the whole run.
```

```markdown
---
name: collect-search
description: Discover Agent/AI trend items from generic manual web search.
---

# Collect Search

Manual/future workflow: this skill describes Codex-assisted generic web search discovery and is not automated by `news-bycodex report` in the MVP pipeline today.

This is separate from the implemented keyword-driven HN Algolia and GitHub API source types.

Input: `configs/keywords.yaml`.

Output: `data/raw/YYYY-MM-DD/search.jsonl`.

Rules:
- Search priority keywords first.
- Keep query text in metadata.
- Exclude generic SEO pages when they match known noise patterns.
- Promote search findings only after normalization and scoring.
- Treat the input/output contract as aspirational until a generic web search workflow is implemented.
```

```markdown
---
name: render-html-report
description: Render processed trend intelligence into the daily HTML report.
---

# Render HTML Report

Input: in-memory `ReportData` assembled by `run_report`.

Output: `reports/YYYY-MM-DD.html`.

Rules:
- Include executive summary, top trends, weak signals, deferred items, and source coverage.
- Preserve links to original sources.
- Mark maturity, impact, and signal strength visibly.
- Disclose source errors carried in `ReportData.source_errors`.
- `data/processed/YYYY-MM-DD/trends.jsonl` and `data/raw/YYYY-MM-DD/errors.jsonl` are persisted audit artifacts, not the renderer's direct inputs in the MVP pipeline.
```

- [ ] **Step 4: Commit**

```powershell
git add memory prompts skills
git commit -m "feat: add Codex harness memory prompts and skills"
```

## Task 9: Full Verification and Live Collection Smoke Run

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Create README usage**

````markdown
# news_bycodex

Codex-native daily Agent/AI trend intelligence harness.

## Local MVP

Install dependencies:

```powershell
uv sync --extra dev
```

Run deterministic fixture mode:

```powershell
uv run news-bycodex report --date 2026-05-03 --offline-fixtures --output-dir reports
```

Run live collection:

```powershell
uv run news-bycodex report --date 2026-05-03 --limit-per-source 5 --output-dir reports
```

Outputs:

- `data/raw/YYYY-MM-DD/`
- `data/processed/YYYY-MM-DD/trends.jsonl`
- `reports/YYYY-MM-DD.html`
````

- [ ] **Step 2: Run full test suite**

Run: `uv run python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Run lint**

Run: `uv run python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 4: Run fixture report**

Run: `uv run news-bycodex report --date 2026-05-03 --offline-fixtures --output-dir reports`

Expected: `reports/2026-05-03.html` exists and includes `Fixture agent launch`.

- [ ] **Step 5: Run live report**

Run: `uv run news-bycodex report --date 2026-05-03 --limit-per-source 5 --output-dir reports`

Expected: `reports/2026-05-03.html` exists. Some source errors are acceptable only when they are recorded in `data/raw/2026-05-03/errors.jsonl` and displayed in the HTML Source Coverage section.

- [ ] **Step 6: Commit**

```powershell
git add README.md
git commit -m "docs: add local harness usage"
```

## Self-Review

- Spec coverage: the plan covers repo-local Codex harness structure, real collection, raw snapshots, normalization, deduplication, scoring, HTML rendering, memory, role prompts, skills, source failure recording, and local execution.
- Type consistency: `SourceConfig`, `RawItem`, `TrendItem`, and `ReportData` are introduced before dependent collectors, analysis, rendering, and pipeline tasks.
- Execution risk: live source behavior can vary. The pipeline preserves errors per source and fixture mode gives deterministic verification.
- Scope boundary: scheduling, hosted dashboards, authenticated X collection, full plugin packaging, and durable MCP servers remain outside this MVP.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-03-agent-trend-harness.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
