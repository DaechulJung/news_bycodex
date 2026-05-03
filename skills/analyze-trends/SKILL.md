---
name: analyze-trends
description: Structure raw Agent/AI news items into categorized, scored trend intelligence.
---

# Analyze Trends

Input: `data/raw/YYYY-MM-DD/*.jsonl` and `memory/*.md`.

Output: `data/processed/YYYY-MM-DD/trends.jsonl`.

Rules:
- Deduplicate by canonical URL first.
- Classify each item by category, maturity, impact, and signal strength.
- Promote strong signals when `signal_strength >= 3`.
- Mark weak signals separately instead of discarding them.
- Preserve source URLs and source names.
