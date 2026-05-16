from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path

from news_bycodex.models import RawItem, TrendItem
from news_bycodex.analysis import sort_trends_by_hotness
from news_bycodex.pipeline import executive_summary, is_core_trend, normalize_trend, run_report


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
        use_seen_db=False,
        codex_agents="off",
    )


def write_fixture_config(directory: Path) -> tuple[Path, Path]:
    sources = directory / "sources.yaml"
    keywords = directory / "keywords.yaml"
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
    return sources, keywords


def make_trend(**overrides) -> TrendItem:
    values = {
        "title": "Viral GPT 5.5 launch",
        "url": "https://example.com/gpt-55",
        "source": "Fixture RSS",
        "summary": "새 LLM/모델 출시 신호입니다.",
        "category": "model",
        "maturity": "released",
        "impact": "low",
        "signal_strength": 1,
        "hotness_score": 50,
        "why_it_matters": "모델 성능과 요금 변화를 확인하세요.",
    }
    values.update(overrides)
    return TrendItem(**values)


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
    assert "Agent/AI 트렌드 리포트" in output.read_text(encoding="utf-8")
    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-03/fixture_rss.jsonl")
    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-03/trends.jsonl")
    review_items = read_jsonl(tmp_path / "data/processed/2026-05-03/editorial_review.jsonl")
    assert raw_items[0]["title"] == "Fixture agent launch"
    assert processed_items[0]["title"] == "Fixture agent launch"
    assert processed_items[0]["quality_score"] >= 1
    assert review_items[0]["reviewer"] == "final_reviewer"


def test_executive_summary_is_brief_korean_core_summary():
    summary = executive_summary(top_count=3, weak_count=2, error_count=1)

    assert "핵심 트렌드 3건" in summary
    assert "관찰 신호 2건" in summary
    assert "수집 이슈 1건" in summary
    assert "Collected" not in summary
    assert len(summary) <= 80


def test_core_trend_includes_viral_low_signal_items():
    assert is_core_trend(make_trend(signal_strength=1, hotness_score=50)) is True
    assert is_core_trend(make_trend(signal_strength=1, hotness_score=20)) is False


def test_offline_fixture_outputs_are_deterministic(tmp_path: Path, monkeypatch):
    first_run = tmp_path / "first"
    second_run = tmp_path / "second"
    first_run.mkdir()
    second_run.mkdir()

    monkeypatch.chdir(first_run)
    first_sources, first_keywords = write_fixture_config(first_run)
    first_output = run_report(make_args(first_run, first_sources, first_keywords))
    first_raw = (first_run / "data/raw/2026-05-03/fixture_rss.jsonl").read_text(
        encoding="utf-8"
    )
    first_html = first_output.read_text(encoding="utf-8")

    monkeypatch.chdir(second_run)
    second_sources, second_keywords = write_fixture_config(second_run)
    second_output = run_report(make_args(second_run, second_sources, second_keywords))
    second_raw = (second_run / "data/raw/2026-05-03/fixture_rss.jsonl").read_text(
        encoding="utf-8"
    )
    second_html = second_output.read_text(encoding="utf-8")

    assert first_raw == second_raw
    assert first_html == second_html
    assert "2026-05-03T00:00:00+00:00" in first_html
    assert "2026-05-03T00:00:00Z" in first_raw


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
  - id: fixture_google_search
    name: Fixture Google Search
    type: google_search
    enabled: true
    url: https://www.googleapis.com/customsearch/v1
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
        "fixture_google_search",
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


def test_run_report_filters_items_older_than_seven_days(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"
    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_source",
        lambda *args: [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Old agent video",
                url="https://example.com/old-agent",
                summary="Old coding agent news",
                published_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Recent agent video",
                url="https://example.com/recent-agent",
                summary="Recent coding agent news",
                published_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
            ),
        ],
    )

    run_report(args)

    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-05/fixture_rss.jsonl")
    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    assert [item["title"] for item in raw_items] == ["Recent agent video"]
    assert [item["title"] for item in processed_items] == ["Recent agent video"]


def test_run_report_excludes_items_already_seen_in_sqlite_state(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"
    args.use_seen_db = True

    def collect_seen_candidate(*args):
        return [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Seen agent launch",
                url="https://example.com/seen-agent",
                summary="Released coding agent framework",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr("news_bycodex.pipeline.collect_source", collect_seen_candidate)

    run_report(args)
    first_processed = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    run_report(args)
    second_raw = read_jsonl(tmp_path / "data/raw/2026-05-05/fixture_rss.jsonl")
    second_processed = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")

    assert len(first_processed) == 1
    assert second_raw == []
    assert second_processed == []
    assert (tmp_path / "data/state/seen_items.sqlite").exists()


def test_run_report_keeps_seen_items_when_seen_db_is_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"

    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_source",
        lambda *args: [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Repeat agent launch",
                url="https://example.com/repeat-agent",
                summary="Released coding agent framework",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            )
        ],
    )

    run_report(args)
    run_report(args)

    second_raw = read_jsonl(tmp_path / "data/raw/2026-05-05/fixture_rss.jsonl")
    second_processed = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    assert [item["title"] for item in second_raw] == ["Repeat agent launch"]
    assert [item["title"] for item in second_processed] == ["Repeat agent launch"]
    assert not (tmp_path / "data/state/seen_items.sqlite").exists()


def test_run_report_bootstraps_seen_state_from_existing_processed_outputs(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"
    args.use_seen_db = True
    previous = tmp_path / "data/processed/2026-05-04/trends.jsonl"
    previous.parent.mkdir(parents=True)
    previous.write_text(
        json.dumps(
            {
                "title": "Previously collected agent launch",
                "url": "https://example.com/previous-agent",
                "source": "Fixture RSS",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_source",
        lambda *args: [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Previously collected agent launch",
                url="https://example.com/previous-agent",
                summary="Released coding agent framework",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            )
        ],
    )

    run_report(args)

    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-05/fixture_rss.jsonl")
    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    assert raw_items == []
    assert processed_items == []


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


def test_run_report_retries_transient_source_timeout(tmp_path: Path, monkeypatch):
    import httpx

    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"
    attempts = {"count": 0}

    def flaky_collect(*args):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Recovered agent harness news",
                url="https://example.com/recovered-agent",
                summary="Released agent harness runtime",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr("news_bycodex.pipeline.collect_source", flaky_collect)

    run_report(args)

    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-05/fixture_rss.jsonl")
    errors = read_jsonl(tmp_path / "data/raw/2026-05-05/errors.jsonl")
    assert attempts["count"] == 2
    assert raw_items[0]["title"] == "Recovered agent harness news"
    assert errors == []


def test_live_rerun_clears_stale_source_output_and_error_log(tmp_path: Path, monkeypatch):
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
    stale_source = tmp_path / "data/raw/2026-05-03/failing_web.jsonl"
    stale_errors = tmp_path / "data/raw/2026-05-03/errors.jsonl"
    stale_source.parent.mkdir(parents=True)
    stale_source.write_text('{"title": "stale fixture"}\n', encoding="utf-8")
    stale_errors.write_text('{"source_id": "old_error"}\n', encoding="utf-8")

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

    assert stale_source.read_text(encoding="utf-8") == ""
    errors = read_jsonl(stale_errors)
    assert len(errors) == 1
    assert errors[0]["source_id"] == "failing_web"


def test_live_client_follows_redirects(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    client_kwargs = {}

    class RecordingClient:
        def __init__(self, *args, **kwargs):
            client_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("news_bycodex.pipeline.httpx.Client", RecordingClient)

    run_report(make_args(tmp_path, sources, keywords))

    assert client_kwargs["follow_redirects"] is True
    assert client_kwargs["timeout"] == 30


def test_run_report_routes_youtube_rss_sources_to_youtube_collector(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = tmp_path / "sources.yaml"
    keywords = tmp_path / "keywords.yaml"
    write_yaml(
        sources,
        """
sources:
  - id: youtube_jocoding
    name: JoCoding YouTube
    type: rss
    enabled: true
    url: https://www.youtube.com/feeds/videos.xml?channel_id=UCQNE2JmbasNYbjGAcuBiRRg
    selectors:
      channel_url: https://www.youtube.com/@jocoding/videos
""",
    )
    write_yaml(keywords, "keywords:\n  - codex\n")
    called = {}

    class RecordingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_collect_youtube_source(client, source, keywords):
        called["source_id"] = source.id
        called["keywords"] = keywords
        return [
            RawItem(
                source_id=source.id,
                source_name=source.name,
                source_type=source.type,
                title="Codex agent video",
                url="https://www.youtube.com/watch?v=abc123agent",
                summary="Codex workflow update",
                published_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
            )
        ]

    monkeypatch.setattr("news_bycodex.pipeline.httpx.Client", RecordingClient)
    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_youtube_source",
        fake_collect_youtube_source,
        raising=False,
    )

    run_report(make_args(tmp_path, sources, keywords, offline_fixtures=False))

    raw_items = read_jsonl(tmp_path / "data/raw/2026-05-03/youtube_jocoding.jsonl")
    errors = read_jsonl(tmp_path / "data/raw/2026-05-03/errors.jsonl")
    assert called == {"source_id": "youtube_jocoding", "keywords": ["codex"]}
    assert raw_items[0]["title"] == "Codex agent video"
    assert errors == []


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
    assert "duplicate_count=2" in related_items
    assert "duplicate_sources=duplicate_rss, duplicate_web" in related_items
    assert any("Duplicate RSS" in item for item in related_items)
    assert any("Duplicate Web" in item for item in related_items)
    assert any("https://example.com/agent" in item for item in related_items)


def test_similar_news_from_different_urls_are_grouped_with_links(tmp_path: Path, monkeypatch):
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
  - id: fixture_web
    name: Fixture Web
    type: web
    enabled: true
    url: https://news.example.com/
    credibility: 0.8
""",
    )
    write_yaml(keywords, "keywords:\n  - agent\n")

    output = run_report(make_args(tmp_path, sources, keywords))

    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-03/trends.jsonl")
    html = output.read_text(encoding="utf-8")
    assert len(processed_items) == 1
    assert any("Fixture RSS: https://example.com/agent" in item for item in processed_items[0]["related_items"])
    assert any(
        "Fixture Web: https://news.example.com/agent" in item
        for item in processed_items[0]["related_items"]
    )
    assert "Fixture agent launch - 근거 및 관련 링크" in html
    assert 'href="https://news.example.com/agent"' in html


def test_normalize_trend_adds_hacker_news_discussion_as_related_source():
    raw = RawItem(
        source_id="hacker_news",
        source_name="Hacker News Algolia",
        source_type="hn_algolia",
        title="Show HN: ByAllo - the online bookstore that runs itself",
        url="https://byallo.com/",
        summary="Momental is an agent harness with MCP handoff.",
        metadata={"discussion_url": "https://news.ycombinator.com/item?id=12345"},
    )

    trend = normalize_trend(raw, raw_items=[raw], credibility=0.8, history_text="")

    assert "Hacker News discussion: https://news.ycombinator.com/item?id=12345" in trend.related_items


def test_low_engagement_hacker_news_showcase_stays_weak_without_corroboration():
    raw = RawItem(
        source_id="hacker_news",
        source_name="Hacker News Algolia",
        source_type="hn_algolia",
        title="Show HN: ByAllo - the online bookstore that runs itself",
        url="https://byallo.com/",
        summary=(
            "Momental is an agent harness with a self-maintaining context graph. "
            "It launched with cloud agents and MCP handoff."
        ),
        metadata={
            "discussion_url": "https://news.ycombinator.com/item?id=12345",
            "points": 4,
            "comments": 0,
        },
    )

    trend = normalize_trend(raw, raw_items=[raw], credibility=0.8, history_text="")
    scored = sort_trends_by_hotness([trend])[0]

    assert scored.signal_strength <= 3
    assert scored.hotness_score < 45
    assert is_core_trend(scored) is False


def test_provider_name_alone_does_not_make_generic_item_core():
    trend = make_trend(
        title="OpenAI and PwC collaborate to reimagine the office of the CFO",
        summary="OpenAI and PwC are partnering to help enterprises automate finance workflows.",
        category="other",
        signal_strength=3,
        impact="medium",
        tags=["#openai", "#workflow"],
    )

    scored = sort_trends_by_hotness([trend])[0]

    assert scored.hotness_score < 45
    assert is_core_trend(scored) is False


def test_run_report_orders_top_trends_by_hotness_not_only_signal_strength(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.date = "2026-05-05"
    monkeypatch.setattr(
        "news_bycodex.pipeline.collect_source",
        lambda *args: [
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="Generic coding agent framework released",
                url="https://example.com/generic-agent",
                summary="Released coding agent framework",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="OpenAI GPT 5.5 model launch",
                url="https://example.com/gpt-55-a",
                summary="OpenAI launched GPT 5.5 for agent workflows",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="GPT 5.5 release for agents",
                url="https://example.com/gpt-55-b",
                summary="GPT 5.5 release coverage",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
            RawItem(
                source_id="fixture_rss",
                source_name="Fixture RSS",
                source_type="rss",
                title="GPT 5.5 launch analysis",
                url="https://example.com/gpt-55-c",
                summary="Model launch analysis",
                published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
        ],
    )

    run_report(args)

    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    assert processed_items[0]["title"] == "OpenAI GPT 5.5 model launch"
    assert processed_items[0]["hotness_score"] > processed_items[1]["hotness_score"]


def test_run_report_full_codex_agents_applies_agent_edits_and_writes_audit(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    sources, keywords = write_fixture_config(tmp_path)
    args = make_args(tmp_path, sources, keywords)
    args.codex_agents = "full"
    args.date = "2026-05-05"
    called = {}

    def fake_codex_workflow(report, raw_items, processed_dir, mode):
        called["mode"] = mode
        called["raw_count"] = len(raw_items)
        edited = report.top_trends[0].model_copy(
            update={
                "summary": "Codex agent edited Korean summary",
                "why_it_matters": "Codex agent added a more useful editorial insight",
            }
        )
        return (
            report.model_copy(update={"top_trends": [edited]}),
            [{"role": "trend_analyst", "status": "applied", "updated_count": 1}],
        )

    monkeypatch.setattr("news_bycodex.pipeline.run_codex_agent_workflow", fake_codex_workflow)

    run_report(args)

    processed_items = read_jsonl(tmp_path / "data/processed/2026-05-05/trends.jsonl")
    audit_items = read_jsonl(tmp_path / "data/processed/2026-05-05/codex_agent_audit.jsonl")
    assert called == {"mode": "full", "raw_count": 1}
    assert processed_items[0]["summary"] == "Codex agent edited Korean summary"
    assert processed_items[0]["why_it_matters"] == "Codex agent added a more useful editorial insight"
    assert audit_items[0]["role"] == "trend_analyst"
