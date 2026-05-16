# news_bycodex

Codex-native daily Agent/AI trend intelligence harness.

Configured source groups include community, research, developer, official product/blog, framework
blogs, web, YouTube RSS feeds, and optional Google Search. The report renders concise Korean-first
summaries for daily review, with agentic/harness engineering treated as a first-class beat.

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

Run the full Codex editorial chain:

```powershell
uv run news-bycodex report --date 2026-05-03 --limit-per-source 5 --codex-agents full
```

`--codex-agents full` runs source reporters, the trend analyst, editor-in-chief, and final
reviewer through `codex exec`. Use `--codex-agents review` when only the final Codex review pass is
needed. If a Codex worker fails or returns invalid JSON, the deterministic report still renders and
the failure is recorded in the audit log.

Google Search collection is enabled in `configs/sources.yaml`. When
`GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` are present, the collector tries Google's
Custom Search JSON API. That API is closed to new customers, so new projects may receive a 403 even
when the API is enabled; in that case, or when credentials are absent, the harness automatically
falls back to 7-day Google News RSS keyword search. Google Trends is not enabled by default because
the official Trends API is currently alpha/early-access; add it as a separate credentialed collector
when access is available.

Outputs:

- `data/raw/YYYY-MM-DD/`
- `data/processed/YYYY-MM-DD/trends.jsonl`
- `data/processed/YYYY-MM-DD/editorial_review.jsonl`
- `data/processed/YYYY-MM-DD/codex_agent_audit.jsonl`
- `data/processed/YYYY-MM-DD/codex_agents/` for Codex worker prompts, inputs, and outputs
- `data/state/seen_items.sqlite` for URLs already reported
- `reports/YYYY-MM-DD.html`

Collection keeps only items in the 7-day window ending on the report date. URLs already present in
the SQLite seen-state database, or in earlier processed reports during bootstrap, are skipped.
Before rendering, the final reviewer checks each trend for summary specificity, insight usefulness,
tag coverage, and source confidence. It writes quality scores, review notes, and revision requests to
the processed outputs.

Harness engineering signals are classified separately when they mention agent harnesses, runtimes,
orchestration, subagents, tool calling, MCP, evaluation, tracing, observability, or durable
execution. These signals receive additional hotness weight so they are not buried under generic AI
news.
