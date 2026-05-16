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
- Treat `harness_engineering` as a first-class category for agent harnesses, runtimes, orchestration, subagents, tool calling, MCP, evaluation, tracing, observability, and durable execution.
- Promote agentic/harness signals when they affect production readiness, developer workflow, reliability, cost, security, or evaluation.
- Promote strong signals when `signal_strength >= 3`.
- Mark weak signals separately instead of discarding them.
- Preserve source URLs and source names.
- `data/raw/YYYY-MM-DD/*.jsonl` is the persisted audit/replay artifact for collected raw items.
- Manual or future replay workflows may use `data/raw/YYYY-MM-DD/*.jsonl` as their input source.
- The automated pipeline currently uses `memory/trend_history.md` for novelty checks.
- `memory/interests.md` and `memory/noise_patterns.md` are editorial guidance for Codex/manual review until they are wired into automated scoring.
