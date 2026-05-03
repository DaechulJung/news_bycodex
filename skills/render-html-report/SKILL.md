---
name: render-html-report
description: Render processed trend intelligence into the daily HTML report.
---

# Render HTML Report

Input: `data/processed/YYYY-MM-DD/trends.jsonl`.

Output: `reports/YYYY-MM-DD.html`.

Rules:
- Include executive summary, top trends, weak signals, deferred items, and source coverage.
- Preserve links to original sources.
- Mark maturity, impact, and signal strength visibly.
- Disclose source errors from `data/raw/YYYY-MM-DD/errors.jsonl`.
