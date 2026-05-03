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
    errors = [
        json.loads(line)
        for line in (tmp_path / "errors.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert rows[0]["title"] == "New coding agent"
    assert errors[0]["source_id"] == "reddit"
    assert errors[0]["message"] == "HTTP 429"
