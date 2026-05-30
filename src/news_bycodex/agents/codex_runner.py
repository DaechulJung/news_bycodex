from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
from typing import Any

from pydantic import ValidationError

from news_bycodex.io import ensure_dir
from news_bycodex.models import RawItem, ReportData, TrendItem


FULL_ROLE_SEQUENCE = [
    "community_reporter",
    "research_reporter",
    "product_reporter",
    "developer_reporter",
    "youtube_reporter",
    "trend_analyst",
    "editor_in_chief",
    "final_reviewer",
]
REVIEW_ROLE_SEQUENCE = ["final_reviewer"]
SOURCE_REPORTER_ROLES = {
    "community_reporter",
    "research_reporter",
    "product_reporter",
    "developer_reporter",
    "youtube_reporter",
}
ALLOWED_TREND_UPDATE_FIELDS = {
    "title",
    "image_url",
    "published_at",
    "summary",
    "detail_summary",
    "category",
    "maturity",
    "impact",
    "signal_strength",
    "hotness_score",
    "tags",
    "tag_flags",
    "why_it_matters",
    "quality_score",
    "revision_requests",
    "review_notes",
    "related_items",
}
CATEGORY_ALIASES = {
    "agent_data_integration": "harness_engineering",
    "data_quality": "benchmark",
    "data_tooling": "tooling",
    "enterprise_agent": "agent_framework",
    "enterprise_ai": "company",
    "event": "company",
    "event_preview": "company",
    "infrastructure": "harness_engineering",
    "marketing": "company",
    "model_analysis": "model",
    "multimodal": "model",
    "observability": "harness_engineering",
    "product_api": "product",
    "program": "company",
    "security": "tooling",
    "workflow": "harness_engineering",
    "workflow_automation": "harness_engineering",
}
MATURITY_ALIASES = {
    "announcement": "released",
    "announced": "released",
    "concept": "prototype",
    "launch": "released",
    "launched": "released",
    "preview": "beta",
    "private_beta": "beta",
}
IMPACT_ALIASES = {
    "critical": "strategic",
    "major": "high",
    "significant": "high",
    "weak": "low",
}
SECTION_KEYS = {
    "top_urls": "top_trends",
    "weak_urls": "weak_signals",
    "deferred_urls": "deferred_items",
}
SAFE_ENV_NAMES = {
    "APPDATA",
    "CODEX_HOME",
    "COMSPEC",
    "HOME",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
}
SECRET_ENV_MARKERS = (
    "API_KEY",
    "AUTH",
    "COOKIE",
    "CREDENTIAL",
    "PASSWORD",
    "SECRET",
    "TOKEN",
)
CODEX_TIMEOUT_ENV = "NEWS_BYCODEX_CODEX_TIMEOUT_SECONDS"


class CodexAgentError(RuntimeError):
    """Raised when a Codex worker process cannot return a usable JSON response."""


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
        )
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def run_worker_process(
    command: list[str],
    *,
    input_text: str,
    timeout_seconds: int,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": cwd,
        "env": env,
        "encoding": "utf-8",
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **popen_kwargs)
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(process.pid)
        raise CodexAgentError(
            f"codex exec timed out after {timeout_seconds}s: {' '.join(command)}"
        ) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout or "", stderr or "")


def codex_timeout_seconds(default: int = 600) -> int:
    raw_value = os.environ.get(CODEX_TIMEOUT_ENV)
    if not raw_value:
        return default
    try:
        timeout = int(raw_value)
    except ValueError:
        return default
    return timeout if timeout > 0 else default


def codex_role_sequence(mode: str) -> list[str]:
    if mode == "off":
        return []
    if mode == "review":
        return REVIEW_ROLE_SEQUENCE.copy()
    if mode == "full":
        return FULL_ROLE_SEQUENCE.copy()
    raise ValueError(f"Unsupported codex agent mode: {mode}")


class CodexAgentRunner:
    def __init__(
        self,
        *,
        workspace: str | Path | None = None,
        prompts_dir: str | Path = "prompts/roles",
        output_dir: str | Path = "data/processed/codex_agents",
        timeout_seconds: int | None = None,
        command: str | None = None,
    ) -> None:
        self.workspace = Path(workspace or Path.cwd())
        self.prompts_dir = Path(prompts_dir)
        self.output_dir = Path(output_dir)
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else codex_timeout_seconds()
        )
        self.command = command or shutil.which("codex.cmd") or shutil.which("codex") or "codex"

    def run(self, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        ensure_dir(self.output_dir)
        role_input_path = self.output_dir / f"{role}_input.json"
        role_output_path = self.output_dir / f"{role}_output.md"
        role_prompt_path = self.output_dir / f"{role}_prompt.md"
        role_input_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        prompt = self.build_prompt(role, payload)
        role_prompt_path.write_text(prompt, encoding="utf-8")
        command = [
            self.command,
            "-C",
            str(self.workspace),
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "exec",
            "--output-last-message",
            str(role_output_path),
            "-",
        ]
        completed = run_worker_process(
            command,
            input_text=prompt,
            timeout_seconds=self.timeout_seconds,
            cwd=self.workspace,
            env=sanitized_environment(),
        )
        if completed.returncode != 0:
            raise CodexAgentError(
                f"codex exec failed for {role}: {completed.stderr or completed.stdout}"
            )
        response_text = (
            role_output_path.read_text(encoding="utf-8")
            if role_output_path.exists()
            else completed.stdout
        )
        try:
            return parse_json_response(response_text)
        except ValueError as exc:
            raise CodexAgentError(f"codex exec returned invalid JSON for {role}: {exc}") from exc

    def build_prompt(self, role: str, payload: dict[str, Any]) -> str:
        role_prompt = load_role_prompt(self.prompts_dir, role)
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
        return (
            "You were dispatched as a Codex subagent inside the news_bycodex daily trend "
            "harness. Do not inspect the repository, ask follow-up questions, or modify files.\n\n"
            f"{role_prompt}\n\n"
            "Review the provided input and return ONLY one JSON object. Do not include Markdown.\n"
            "Allowed response fields:\n"
            "- notes: array of short strings\n"
            "- trend_updates: array of objects with a url field; allowed fields are summary, "
            "detail_summary, why_it_matters, category, maturity, impact, signal_strength, "
            "hotness_score, tags, tag_flags, quality_score, revision_requests, review_notes, "
            "related_items\n"
            "- detail_summary is the expanded clickable article body. It must summarize the "
            "original news/content, not the category. Use Korean and preserve concrete source "
            "details. Include 원문 상세 요약 with 5-8 bullets when source text has enough detail, "
            "plus 인사이트 and 확인 포인트. Do not replace source details with category-level filler.\n"
            "- category must be one of: model, agent_framework, harness_engineering, "
            "coding_agent, research, product, tooling, benchmark, company, other\n"
            "- maturity must be one of: rumor, prototype, beta, released, adopted\n"
            "- impact must be one of: low, medium, high, strategic\n"
            "- top_urls, weak_urls, deferred_urls: arrays of URLs for section ordering\n"
            "- editorial_reviews: array of review records\n"
            "Keep card summaries concise, but make detail_summary information-dense and "
            "source-grounded. Do not invent facts not present in sources.\n\n"
            f"Input JSON:\n{payload_json}\n"
        )


def load_role_prompt(prompts_dir: Path, role: str) -> str:
    path = prompts_dir / f"{role}.md"
    if not path.exists():
        return f"# {role}\n\nAct within this editorial role for the daily Agent/AI trend report."
    return path.read_text(encoding="utf-8")


def sanitized_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    source = environ or os.environ
    sanitized: dict[str, str] = {}
    for key, value in source.items():
        upper = key.upper()
        if any(marker in upper for marker in SECRET_ENV_MARKERS):
            continue
        if upper in SAFE_ENV_NAMES:
            sanitized[key] = value
    return sanitized


def parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty response")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response must be a JSON object")
    return parsed


def run_codex_agent_workflow(
    report: ReportData,
    raw_items: list[RawItem],
    processed_dir: Path,
    mode: str,
    *,
    runner: CodexAgentRunner | None = None,
) -> tuple[ReportData, list[dict[str, Any]]]:
    roles = codex_role_sequence(mode)
    if not roles:
        return report, []
    agent_output_dir = processed_dir / "codex_agents"
    active_runner = runner or CodexAgentRunner(output_dir=agent_output_dir)
    current_report = report
    audit_records: list[dict[str, Any]] = []
    for role in roles:
        payload = build_agent_payload(role, current_report, raw_items, mode)
        try:
            response = active_runner.run(role, payload)
            current_report, audit = apply_codex_agent_response(current_report, role, response)
        except Exception as exc:
            audit = {
                "role": role,
                "status": "failed",
                "message": f"{type(exc).__name__}: {exc}",
            }
        audit_records.append(audit)
    return current_report, audit_records


def build_agent_payload(
    role: str,
    report: ReportData,
    raw_items: list[RawItem],
    mode: str,
) -> dict[str, Any]:
    selected_raw_items = (
        raw_items_for_role(role, raw_items) if role in SOURCE_REPORTER_ROLES else raw_items
    )
    return {
        "mode": mode,
        "role": role,
        "report": compact_report(report),
        "raw_items": [compact_raw_item(item) for item in selected_raw_items[:80]],
    }


def raw_items_for_role(role: str, raw_items: list[RawItem]) -> list[RawItem]:
    return [item for item in raw_items if raw_item_matches_role(item, role)]


def raw_item_matches_role(item: RawItem, role: str) -> bool:
    source = f"{item.source_id} {item.source_name} {item.source_type}".lower()
    if role == "community_reporter":
        return any(marker in source for marker in ["hacker", "reddit", "geeknews", "community"])
    if role == "research_reporter":
        return any(marker in source for marker in ["arxiv", "papers", "benchmark", "research"])
    if role == "developer_reporter":
        return any(
            marker in source for marker in ["github", "developer", "langchain", "llamaindex"]
        )
    if role == "youtube_reporter":
        return "youtube" in source
    if role == "product_reporter":
        product_markers = ["openai", "google", "anthropic", "hugging", "product", "xai"]
        return any(marker in source for marker in product_markers)
    return True


def compact_report(report: ReportData) -> dict[str, Any]:
    return {
        "date": report.date,
        "generated_at": report.generated_at.isoformat(),
        "executive_summary": report.executive_summary,
        "top_trends": [compact_trend(item) for item in report.top_trends],
        "weak_signals": [compact_trend(item) for item in report.weak_signals],
        "deferred_items": [compact_trend(item) for item in report.deferred_items],
        "source_errors": report.source_errors,
        "editorial_reviews": report.editorial_reviews,
    }


def compact_raw_item(item: RawItem) -> dict[str, Any]:
    return {
        "source_id": item.source_id,
        "source_name": item.source_name,
        "source_type": item.source_type,
        "title": item.title,
        "url": item.url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "summary": truncate_for_prompt(item.summary, 2000),
        "metadata": compact_metadata(item.metadata),
    }


def compact_trend(item: TrendItem) -> dict[str, Any]:
    return {
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "summary": truncate_for_prompt(item.summary, 1000),
        "detail_summary": truncate_for_prompt(item.detail_summary, 2400),
        "category": item.category,
        "maturity": item.maturity,
        "impact": item.impact,
        "signal_strength": item.signal_strength,
        "hotness_score": item.hotness_score,
        "tags": item.tags,
        "tag_flags": item.tag_flags,
        "why_it_matters": truncate_for_prompt(item.why_it_matters, 700),
        "quality_score": item.quality_score,
        "revision_requests": item.revision_requests,
        "review_notes": item.review_notes,
        "related_items": item.related_items,
    }


def compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            compacted[key] = truncate_for_prompt(value, 300)
        elif isinstance(value, (int, float, bool)) or value is None:
            compacted[key] = value
        elif isinstance(value, list):
            compacted[key] = [truncate_for_prompt(str(item), 160) for item in value[:10]]
        else:
            compacted[key] = truncate_for_prompt(str(value), 300)
    return compacted


def truncate_for_prompt(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def apply_codex_agent_response(
    report: ReportData,
    role: str,
    response: dict[str, Any],
) -> tuple[ReportData, dict[str, Any]]:
    trends_by_url = all_trends_by_url(report)
    original_sections = section_by_url(report)
    errors: list[str] = []
    updated_count = apply_trend_updates(trends_by_url, response.get("trend_updates"), errors)
    top_trends, weak_signals, deferred_items = apply_section_updates(
        report, trends_by_url, response
    )
    moved_count = count_section_moves(
        original_sections,
        {
            **{item.url: "top_trends" for item in top_trends},
            **{item.url: "weak_signals" for item in weak_signals},
            **{item.url: "deferred_items" for item in deferred_items},
        },
    )
    editorial_reviews = report.editorial_reviews + normalize_editorial_reviews(
        response.get("editorial_reviews")
    )
    updated_report = report.model_copy(
        update={
            "top_trends": top_trends,
            "weak_signals": weak_signals,
            "deferred_items": deferred_items,
            "editorial_reviews": editorial_reviews,
        }
    )
    audit = {
        "role": role,
        "status": "applied" if not errors else "applied_with_warnings",
        "updated_count": updated_count,
        "moved_count": moved_count,
        "review_count": len(editorial_reviews) - len(report.editorial_reviews),
        "notes": normalize_notes(response.get("notes")),
        "errors": errors,
    }
    return updated_report, audit


def all_trends_by_url(report: ReportData) -> dict[str, TrendItem]:
    trends: dict[str, TrendItem] = {}
    for item in report.top_trends + report.weak_signals + report.deferred_items:
        trends[item.url] = item
    return trends


def section_by_url(report: ReportData) -> dict[str, str]:
    return {
        **{item.url: "top_trends" for item in report.top_trends},
        **{item.url: "weak_signals" for item in report.weak_signals},
        **{item.url: "deferred_items" for item in report.deferred_items},
    }


def apply_trend_updates(
    trends_by_url: dict[str, TrendItem],
    trend_updates: Any,
    errors: list[str],
) -> int:
    if not isinstance(trend_updates, list):
        return 0
    updated_count = 0
    for update in trend_updates:
        if not isinstance(update, dict):
            errors.append("trend_update_not_object")
            continue
        update = normalize_trend_update_shape(update)
        url = str(update.get("url", "")).strip()
        if not url or url not in trends_by_url:
            errors.append(f"unknown_trend_url:{url}")
            continue
        fields = normalize_trend_update_fields(update)
        if not fields:
            continue
        current = trends_by_url[url]
        data = current.model_dump()
        data.update(fields)
        try:
            trends_by_url[url] = TrendItem.model_validate(data)
        except ValidationError as exc:
            errors.append(f"invalid_trend_update:{url}:{exc.errors()[0]['msg']}")
            continue
        updated_count += 1
    return updated_count


def normalize_trend_update_fields(update: dict[str, Any]) -> dict[str, Any]:
    fields = {
        key: value
        for key, value in update.items()
        if key in ALLOWED_TREND_UPDATE_FIELDS and value is not None
    }
    coerce_enum_alias(fields, "category", CATEGORY_ALIASES)
    coerce_enum_alias(fields, "maturity", MATURITY_ALIASES)
    coerce_enum_alias(fields, "impact", IMPACT_ALIASES)
    if isinstance(fields.get("tags"), list):
        fields["tags"] = [normalize_tag(str(tag)) for tag in fields["tags"] if str(tag).strip()]
    return fields


def normalize_trend_update_shape(update: dict[str, Any]) -> dict[str, Any]:
    if "url" in update:
        return update
    if len(update) == 1:
        url, value = next(iter(update.items()))
        if (
            isinstance(url, str)
            and url.startswith(("http://", "https://"))
            and isinstance(value, dict)
        ):
            return {"url": url, **value}
    return update


def coerce_enum_alias(fields: dict[str, Any], field_name: str, aliases: dict[str, str]) -> None:
    value = fields.get(field_name)
    if isinstance(value, str):
        fields[field_name] = aliases.get(value.strip().lower(), value)


def normalize_tag(tag: str) -> str:
    stripped = tag.strip()
    return stripped if stripped.startswith("#") else f"#{stripped}"


def apply_section_updates(
    report: ReportData,
    trends_by_url: dict[str, TrendItem],
    response: dict[str, Any],
) -> tuple[list[TrendItem], list[TrendItem], list[TrendItem]]:
    if not any(key in response for key in SECTION_KEYS):
        return (
            [trends_by_url[item.url] for item in report.top_trends],
            [trends_by_url[item.url] for item in report.weak_signals],
            [trends_by_url[item.url] for item in report.deferred_items],
        )
    assigned: set[str] = set()
    top_trends = items_for_urls(response.get("top_urls"), trends_by_url, assigned)
    weak_signals = items_for_urls(response.get("weak_urls"), trends_by_url, assigned)
    deferred_items = items_for_urls(response.get("deferred_urls"), trends_by_url, assigned)
    top_trends.extend(unassigned_original_items(report.top_trends, trends_by_url, assigned))
    weak_signals.extend(unassigned_original_items(report.weak_signals, trends_by_url, assigned))
    deferred_items.extend(unassigned_original_items(report.deferred_items, trends_by_url, assigned))
    return top_trends, weak_signals, deferred_items


def items_for_urls(
    urls: Any,
    trends_by_url: dict[str, TrendItem],
    assigned: set[str],
) -> list[TrendItem]:
    if not isinstance(urls, list):
        return []
    items: list[TrendItem] = []
    for url_value in urls:
        url = str(url_value).strip()
        if url in trends_by_url and url not in assigned:
            items.append(trends_by_url[url])
            assigned.add(url)
    return items


def unassigned_original_items(
    items: list[TrendItem],
    trends_by_url: dict[str, TrendItem],
    assigned: set[str],
) -> list[TrendItem]:
    output: list[TrendItem] = []
    for item in items:
        if item.url not in assigned and item.url in trends_by_url:
            output.append(trends_by_url[item.url])
            assigned.add(item.url)
    return output


def count_section_moves(original: dict[str, str], updated: dict[str, str]) -> int:
    return sum(1 for url, section in updated.items() if original.get(url) != section)


def normalize_editorial_reviews(reviews: Any) -> list[dict[str, Any]]:
    if not isinstance(reviews, list):
        return []
    return [review for review in reviews if isinstance(review, dict)]


def normalize_notes(notes: Any) -> list[str]:
    if not isinstance(notes, list):
        return []
    return [str(note) for note in notes if str(note).strip()]
