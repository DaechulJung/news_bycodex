---
name: analyze-trends
description: Structure raw Agent/AI news items into categorized, scored trend intelligence.
---

# Analyze Trends

Input: `data/raw/YYYY-MM-DD/*.jsonl` and `memory/trend_history.md`.

Output: `data/processed/YYYY-MM-DD/trends.jsonl`.

Rules:
- Deduplicate by canonical URL first.
- Classify each item by category, maturity, impact, and signal strength.
- Promote strong signals when `signal_strength >= 3`.
- Mark weak signals separately instead of discarding them.
- Preserve source URLs and source names.
- The automated pipeline currently uses `memory/trend_history.md` for novelty checks.
- `memory/interests.md` and `memory/noise_patterns.md` are editorial guidance for Codex/manual review until they are wired into automated scoring.
