from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path

from news_bycodex.models import RawItem
from news_bycodex.pipeline import run_report


def write_yaml(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def make_args(tmp_path: Path, sources: Path, keywords: Path, *, offline_fixtures: bool = True):
    return Namespace(
        date="2026-05-03",
        limit_per_source=5,
        sources=str(sources),
        keywords=str(keywords),
        output_dir=str(tmp_path / "reports"),
        offline_fixtures=offline_fixtures,
    )


def test_run_report_with_offline_fixtures_writes_raw_and_processed_outputs(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
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
    )
    write_yaml(keywords, "keywords:\n  - agent\n")

    output = run_report(make_args(tmp_path, sources, keywords))

    assert output.exists()
    assert "Agent/AI Trend Report" in output.read_text(encoding="utf-8")
    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-03/fixture_rss.jsonl")
    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-03/trends.jsonl")
    assert raw_items[0]["title"] == "Fixture agent launch"
    assert processed_items[0]["title"] == "Fixture agent launch"


def test_offline_fixtures_do_not_call_network_for_any_supported_source_type(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
        """
sources:
  - id: fixture_hn
    name: Fixture HN
    type: hn_algolia
    enabled: true
    url: https://hn.algolia.com/api/v1/search_by_date
  - id: fixture_arxiv
    name: Fixture arXiv
    type: arxiv
    enabled: true
    url: https://export.arxiv.org/api/query
  - id: fixture_github
    name: Fixture GitHub
    type: github_search
    enabled: true
    url: https://api.github.com/search/repositories
  - id: fixture_reddit
    name: Fixture Reddit
    type: reddit_json
    enabled: true
    url: https://www.reddit.com/r/MachineLearning/new.json
  - id: fixture_rss
    name: Fixture RSS
    type: rss
    enabled: true
    url: https://example.com/rss.xml
  - id: fixture_web
    name: Fixture Web
    type: web
    enabled: true
    url: https://example.com/
""",
    )
    write_yaml(keywords, "keywords:\n  - agent\n")

    class NoNetworkClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            raise AssertionError("offline fixture mode must not call the network")

    monkeypatch.setattr("news_bycodex.pipeline.httpx.Client", NoNetworkClient)

    output = run_report(make_args(tmp_path, sources, keywords))

    assert output.exists()
    for source_id in [
        "fixture_hn",
        "fixture_arxiv",
        "fixture_github",
        "fixture_reddit",
        "fixture_rss",
        "fixture_web",
    ]:
        assert (tmp_path / f"data/raw/2026-05-03/{source_id}.jsonl").exists()


def test_limit_per_source_caps_raw_and_processed_outputs(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
        """
sources:
  - id: fixture_rss
    name: Fixture RSS
    type: rss
    enabled: true
    url: https://example.com/rss.xml
    limit: 5
""",
    )
    write_yaml(keywords, "keywords:\n  - agent\n")
    args = make_args(tmp_path, sources, keywords)
    args.limit_per_source = 1
    collected_at = datetime.now(timezone.utc)
    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_source",
        lambda *args: [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="First agent launch",
                url="https://example.com/agent/1",
                summary="Released coding agent framework",
                collected_at=collected_at,
            ),
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Second agent launch",
                url="https://example.com/agent/2",
                summary="Released coding agent framework",
                collected_at=collected_at,
            ),
        ],
    )

    run_report(args)

    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-03/fixture_rss.jsonl")
    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-03/trends.jsonl")
    assert len(raw_items) == 1
    assert len(processed_items) == 1


def test_source_collection_errors_are_recorded(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
        """
sources:
  - id: failing_web
    name: Failing Web
    type: web
    enabled: true
    url: https://example.com/
""",
    )
    write_yaml(keywords, "keywords:\n  - agent\n")

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("news_bycodex.pipeline.httpx.Client", FailingClient)

    run_report(make_args(tmp_path, sources, keywords, offline_fixtures=False))

    errors = read_jsonl(tmp_path / "data/raw/2026-05-03/errors.jsonl")
    assert errors[0]["source_id"] == "failing_web"
    assert "RuntimeError: boom" in errors[0]["message"]
    report_html = (tmp_path / "reports/2026-05-03.html").read_text(encoding="utf-8")
    assert "failing_web" in report_html


def test_duplicate_evidence_is_preserved_in_processed_trends(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
        """
sources:
  - id: duplicate_rss
    name: Duplicate RSS
    type: rss
    enabled: true
    url: https://example.com/rss.xml
    credibility: 0.9
  - id: duplicate_web
    name: Duplicate Web
    type: web
    enabled: true
    url: https://example.com/
    credibility: 0.8
""",
    )
    write_yaml(keywords, "keywords:\n  - agent\n")

    run_report(make_args(tmp_path, sources, keywords))

    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-03/trends.jsonl")
    related_items = processed_items[0]["related_items"]
    assert any("Duplicate RSS" in item for item in related_items)
    assert any("Duplicate Web" in item for item in related_items)
    assert any("https://example.com/agent" in item for item in related_items)
