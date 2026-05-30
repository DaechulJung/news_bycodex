from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from news_bycodex.agents.codex_runner import (
    CodexAgentError,
    CodexAgentRunner,
    apply_codex_agent_response,
    codex_role_sequence,
)
from news_bycodex.models import ReportData, TrendItem


def make_trend(**overrides) -> TrendItem:
    values = {
        "title": "OpenAI GPT 5.5 launch",
        "url": "https://example.com/gpt-55",
        "source": "Fixture Source",
        "summary": "Original summary",
        "category": "model",
        "maturity": "released",
        "impact": "high",
        "signal_strength": 4,
        "hotness_score": 60,
        "tags": ["#model"],
        "tag_flags": {"model": True},
        "why_it_matters": "Original insight",
    }
    values.update(overrides)
    return TrendItem(**values)


def make_report() -> ReportData:
    return ReportData(
        date="2026-05-05",
        generated_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        executive_summary="summary",
        top_trends=[make_trend()],
        weak_signals=[
            make_trend(
                title="Codex CLI goal update",
                url="https://example.com/codex-goal",
                category="coding_agent",
                hotness_score=30,
                signal_strength=2,
            )
        ],
        deferred_items=[],
    )


def test_full_mode_runs_source_roles_then_editorial_roles():
    assert codex_role_sequence("full") == [
        "community_reporter",
        "research_reporter",
        "product_reporter",
        "developer_reporter",
        "youtube_reporter",
        "trend_analyst",
        "editor_in_chief",
        "final_reviewer",
    ]


def test_review_mode_runs_only_final_reviewer():
    assert codex_role_sequence("review") == ["final_reviewer"]


def test_apply_codex_agent_response_updates_trend_fields_and_sections():
    report = make_report()
    response = {
        "trend_updates": [
            {
                "url": "https://example.com/codex-goal",
                "summary": "Codex subagent rewrote this as a concise Korean summary",
                "detail_summary": "핵심 정리\n- Codex subagent wrote detailed Korean context.",
                "why_it_matters": "Codex subagent added a concrete operational insight",
                "category": "coding_agent",
                "impact": "strategic",
                "signal_strength": 5,
                "hotness_score": 92,
                "tags": ["#coding_agent", "#openai", "#cli"],
                "tag_flags": {"coding_agent": True, "openai": True, "cli": True},
            }
        ],
        "top_urls": ["https://example.com/codex-goal", "https://example.com/gpt-55"],
        "weak_urls": [],
        "deferred_urls": [],
        "editorial_reviews": [
            {
                "reviewer": "codex_final_reviewer",
                "title": "Codex CLI goal update",
                "status": "approved",
            }
        ],
    }

    updated, audit = apply_codex_agent_response(report, "editor_in_chief", response)

    assert audit["role"] == "editor_in_chief"
    assert audit["updated_count"] == 1
    assert updated.top_trends[0].url == "https://example.com/codex-goal"
    assert (
        updated.top_trends[0].summary == "Codex subagent rewrote this as a concise Korean summary"
    )
    assert (
        updated.top_trends[0].detail_summary
        == "핵심 정리\n- Codex subagent wrote detailed Korean context."
    )
    assert updated.top_trends[0].impact == "strategic"
    assert updated.top_trends[0].tags == ["#coding_agent", "#openai", "#cli"]
    assert updated.editorial_reviews[0]["reviewer"] == "codex_final_reviewer"


def test_apply_codex_agent_response_accepts_url_keyed_updates_and_category_aliases():
    report = make_report()
    response = {
        "trend_updates": [
            {
                "https://example.com/gpt-55": {
                    "summary": "URL-keyed update shape from a Codex worker",
                    "category": "infrastructure",
                    "tags": ["harness_engineering", "#agentic"],
                }
            }
        ]
    }

    updated, audit = apply_codex_agent_response(report, "trend_analyst", response)

    assert audit["status"] == "applied"
    assert audit["errors"] == []
    assert updated.top_trends[0].summary == "URL-keyed update shape from a Codex worker"
    assert updated.top_trends[0].category == "harness_engineering"
    assert updated.top_trends[0].tags == ["#harness_engineering", "#agentic"]


def test_codex_runner_places_global_flags_before_exec(tmp_path: Path, monkeypatch):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "trend_analyst.md").write_text("# Trend Analyst", encoding="utf-8")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"notes": ["ok"]}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("news_bycodex.agents.codex_runner.run_worker_process", fake_run)
    runner = CodexAgentRunner(
        workspace=tmp_path,
        prompts_dir=prompts,
        output_dir=tmp_path / "out",
        command="codex",
    )

    assert runner.run("trend_analyst", {"report": {}}) == {"notes": ["ok"]}

    command = captured["command"]
    exec_index = command.index("exec")
    assert command.index("--ask-for-approval") < exec_index
    assert command.index("--sandbox") < exec_index
    assert command.index("-C") < exec_index


def test_codex_runner_kills_worker_process_tree_on_timeout(tmp_path: Path, monkeypatch):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "trend_analyst.md").write_text("# Trend Analyst", encoding="utf-8")
    killed = []

    class TimeoutProcess:
        pid = 12345
        returncode = None

        def communicate(self, **kwargs):
            raise subprocess.TimeoutExpired(cmd=["codex"], timeout=1)

    monkeypatch.setattr(
        "news_bycodex.agents.codex_runner.subprocess.Popen",
        lambda *args, **kwargs: TimeoutProcess(),
    )
    monkeypatch.setattr(
        "news_bycodex.agents.codex_runner.terminate_process_tree",
        lambda pid: killed.append(pid),
    )
    runner = CodexAgentRunner(
        workspace=tmp_path,
        prompts_dir=prompts,
        output_dir=tmp_path / "out",
        timeout_seconds=1,
        command="codex",
    )

    with pytest.raises(CodexAgentError, match="timed out"):
        runner.run("trend_analyst", {"report": {}})

    assert killed == [12345]


def test_codex_runner_reads_timeout_from_environment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NEWS_BYCODEX_CODEX_TIMEOUT_SECONDS", "45")

    runner = CodexAgentRunner(workspace=tmp_path)

    assert runner.timeout_seconds == 45


def test_codex_runner_prompt_requires_source_grounded_detailed_summary(tmp_path: Path):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "trend_analyst.md").write_text("# Trend Analyst", encoding="utf-8")
    runner = CodexAgentRunner(workspace=tmp_path, prompts_dir=prompts, output_dir=tmp_path / "out")

    prompt = runner.build_prompt("trend_analyst", {"raw_items": []})

    assert "원문 상세 요약" in prompt
    assert "5-8" in prompt
    assert "Do not replace source details with category-level filler" in prompt
