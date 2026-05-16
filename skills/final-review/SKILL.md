---
name: final-review
description: Run the final editor quality gate for Agent/AI trend reports, including per-item review, revision routing, quality scoring, and publication readiness checks before HTML rendering.
---

# Final Review

Input: in-memory `ReportData` after trend analysis and grouping, before HTML rendering.

Output:
- Reviewed `TrendItem` objects with `quality_score`, `revision_requests`, and `review_notes`.
- `data/processed/YYYY-MM-DD/editorial_review.jsonl` as the editorial audit trail.

Rules:
- Act as the final editor, not another collector.
- Check every trend for specific Korean summary, useful insight, source clarity, tag coverage, and corroboration.
- Request revisions from the right role:
  - `Trend Analyst`: generic summary, generic insight, missing or weak tags.
  - `Collector Agent`: strong single-source items that need a supporting source.
  - `Editor Agent`: duplicate grouping, ranking, or section-placement issues.
  - `HTML Publisher`: readability or layout issues in rendered output.
- Keep summaries short and factual. Avoid raw copied body text.
- Keep insights decision-oriented: adoption impact, risk, verification need, cost, security, or workflow change.
- Do not publish items with unresolved source ambiguity when they are presented as core trends.
- Treat search engines and aggregators as discovery channels, not provider evidence.
- Do not infer model/provider launches from incidental runtime mentions inside a harness or product story.
- Downgrade or flag low-engagement community items and core single-source items from GitHub, YouTube, Papers with Code, or search unless corroborated.
