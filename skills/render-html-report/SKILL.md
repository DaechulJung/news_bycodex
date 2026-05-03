---
name: render-html-report
description: Render processed trend intelligence into the daily HTML report.
---

# Render HTML Report

Input: in-memory `ReportData` assembled by `run_report`.

Output: `reports/YYYY-MM-DD.html`.

Rules:
- Include executive summary, top trends, weak signals, deferred items, and source coverage.
- Preserve links to original sources.
- Mark maturity, impact, and signal strength visibly.
- Disclose source errors carried in `ReportData.source_errors`.
- `data/processed/YYYY-MM-DD/trends.jsonl` and `data/raw/YYYY-MM-DD/errors.jsonl` are persisted audit artifacts, not the renderer's direct inputs in the MVP pipeline.
